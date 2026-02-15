"""Reaper state tracking.

Caches the current state of Reaper (tracks, transport, etc.)
so the display can render without polling. Updated by the OSC
feedback server.
"""

import logging
import threading

log = logging.getLogger("push2reaper.reaper.state")


class TrackInfo:
    """State for a single track."""

    __slots__ = ("index", "name", "volume", "pan", "mute", "solo",
                 "rec_arm", "selected", "vu", "vu_l", "vu_r",
                 "volume_str", "pan_str", "color", "automode", "sends")

    def __init__(self, index: int):
        self.index = index
        self.name = f"Track {index}"
        self.volume = 0.716  # ~0 dB default
        self.pan = 0.5       # center
        self.mute = False
        self.solo = False
        self.rec_arm = False
        self.selected = False
        self.vu = 0.0
        self.vu_l = 0.0
        self.vu_r = 0.0
        self.volume_str = "0.0 dB"
        self.pan_str = "<C>"
        self.color = None  # RGB tuple (r, g, b) from Reaper, or None for default
        self.automode = 0  # 0=trim, 1=read, 2=touch, 3=write, 4=latch
        self.sends: list[dict] = []  # [{name, volume, volume_str, pan}, ...]


class FXInfo:
    """State for a single FX plugin on a track."""

    __slots__ = ("index", "name", "params")

    def __init__(self, index: int):
        self.index = index
        self.name = f"FX {index + 1}"
        self.params: list[dict] = []  # [{name, value}, ...]


class ReaperState:
    """Thread-safe cache of Reaper DAW state."""

    def __init__(self, event_bus=None, num_tracks: int = 64):
        self.event_bus = event_bus
        self._lock = threading.Lock()

        # Pre-allocate tracks (1-indexed to match Reaper OSC)
        self.tracks: dict[int, TrackInfo] = {}
        for i in range(1, num_tracks + 1):
            self.tracks[i] = TrackInfo(i)

        # Transport state
        self.playing = False
        self.recording = False
        self.paused = False
        self.repeat = False
        self.tempo = 120.0
        self.tempo_str = "120.00"
        self.time_str = "0:00.000"
        self.beat_str = "1.1.00"

        # Master
        self.master_volume = 0.716
        self.master_pan = 0.5
        self.master_vu = 0.0
        self.master_volume_str = "0.0 dB"

        # Device bank tracking
        self.bank_offset = 0  # 0-indexed: track 1 starts at offset 0
        self.selected_track = 1

        # FX state per track: {track_num: [FXInfo, ...]}
        self.fx: dict[int, list[FXInfo]] = {}

        # Dirty flag for display updates
        self._dirty = True

    def get_bank_tracks(self) -> list[TrackInfo]:
        """Get the 8 tracks in the current bank."""
        with self._lock:
            start = self.bank_offset + 1  # 1-indexed
            return [self.tracks.get(i, TrackInfo(i)) for i in range(start, start + 8)]

    def update_track(self, track_num: int, **kwargs) -> None:
        """Update a track's parameters."""
        with self._lock:
            if track_num not in self.tracks:
                self.tracks[track_num] = TrackInfo(track_num)
            track = self.tracks[track_num]
            for key, value in kwargs.items():
                if hasattr(track, key):
                    setattr(track, key, value)
            self._dirty = True

        if self.event_bus:
            self.event_bus.publish("state_changed", {"type": "track", "track": track_num})

    def update_transport(self, **kwargs) -> None:
        """Update transport state."""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            self._dirty = True

        if self.event_bus:
            self.event_bus.publish("state_changed", {"type": "transport"})

    def update_master(self, **kwargs) -> None:
        """Update master channel state."""
        with self._lock:
            for key, value in kwargs.items():
                attr = f"master_{key}"
                if hasattr(self, attr):
                    setattr(self, attr, value)
            self._dirty = True

        if self.event_bus:
            self.event_bus.publish("state_changed", {"type": "master"})

    def update_send(self, track_num: int, send_idx: int, **kwargs) -> None:
        """Update a track's send parameters."""
        with self._lock:
            if track_num not in self.tracks:
                self.tracks[track_num] = TrackInfo(track_num)
            track = self.tracks[track_num]
            # Extend sends list if needed
            while len(track.sends) <= send_idx:
                track.sends.append({
                    "name": f"Send {len(track.sends) + 1}",
                    "volume": 0.0,
                    "volume_str": "-inf dB",
                    "pan": 0.5,
                })
            track.sends[send_idx].update(kwargs)
            self._dirty = True

        if self.event_bus:
            self.event_bus.publish("state_changed", {
                "type": "send", "track": track_num, "send": send_idx
            })

    def update_fx(self, track_num: int, fx_idx: int, **kwargs) -> None:
        """Update FX plugin info."""
        with self._lock:
            if track_num not in self.fx:
                self.fx[track_num] = []
            fx_list = self.fx[track_num]
            while len(fx_list) <= fx_idx:
                fx_list.append(FXInfo(len(fx_list)))
            for key, value in kwargs.items():
                if hasattr(fx_list[fx_idx], key):
                    setattr(fx_list[fx_idx], key, value)
            self._dirty = True

        if self.event_bus:
            self.event_bus.publish("state_changed", {
                "type": "fx", "track": track_num, "fx": fx_idx
            })

    def update_fx_param(self, track_num: int, fx_idx: int,
                        param_idx: int, **kwargs) -> None:
        """Update a specific FX parameter."""
        with self._lock:
            if track_num not in self.fx:
                self.fx[track_num] = []
            fx_list = self.fx[track_num]
            while len(fx_list) <= fx_idx:
                fx_list.append(FXInfo(len(fx_list)))
            fx = fx_list[fx_idx]
            while len(fx.params) <= param_idx:
                fx.params.append({"name": f"Param {len(fx.params) + 1}", "value": 0.0})
            fx.params[param_idx].update(kwargs)
            self._dirty = True

        if self.event_bus:
            self.event_bus.publish("state_changed", {
                "type": "fx_param", "track": track_num,
                "fx": fx_idx, "param": param_idx
            })

    def set_bank(self, offset: int) -> None:
        """Set the bank offset (0-indexed)."""
        with self._lock:
            self.bank_offset = max(0, offset)
            self._dirty = True
        if self.event_bus:
            self.event_bus.publish("state_changed", {"type": "bank"})

    def next_bank(self) -> None:
        self.set_bank(self.bank_offset + 8)

    def prev_bank(self) -> None:
        self.set_bank(self.bank_offset - 8)

    def consume_dirty(self) -> bool:
        """Check and clear dirty flag. Returns True if state changed."""
        with self._lock:
            was_dirty = self._dirty
            self._dirty = False
            return was_dirty
