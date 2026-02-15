"""Reaper OSC client.

Sends OSC messages to Reaper DAW for transport control,
track parameters, navigation, etc.
"""

import logging
from pythonosc.udp_client import SimpleUDPClient

log = logging.getLogger("push2reaper.reaper.osc_client")

# Encoder sensitivity: how much to change volume/pan per encoder tick
VOLUME_STEP = 0.015  # ~1.5% per tick
PAN_STEP = 0.02      # ~2% per tick


class ReaperOSCClient:
    """Sends OSC messages to Reaper DAW."""

    def __init__(self, ip: str = "127.0.0.1", port: int = 8000):
        self.ip = ip
        self.port = port
        self._client: SimpleUDPClient | None = None

    def connect(self) -> None:
        self._client = SimpleUDPClient(self.ip, self.port)
        log.info("OSC client ready → %s:%d", self.ip, self.port)

    def _send(self, address: str, *args) -> None:
        if self._client is None:
            log.warning("OSC client not connected, ignoring: %s", address)
            return
        value = list(args) if args else []
        log.debug("OSC SEND: %s %s", address, value)
        self._client.send_message(address, value)

    # --- Transport ---

    def play(self) -> None:
        self._send("/play")

    def stop(self) -> None:
        self._send("/stop")

    def record(self) -> None:
        self._send("/record")

    def pause(self) -> None:
        self._send("/pause")

    def repeat(self) -> None:
        self._send("/repeat")

    def click(self) -> None:
        """Toggle metronome."""
        self._send("/click")

    # --- Track volume/pan (normalized 0.0-1.0) ---

    def set_track_volume(self, track_num: int, value: float) -> None:
        """Set absolute track volume (0.0-1.0)."""
        value = max(0.0, min(1.0, value))
        self._send(f"/track/{track_num}/volume", value)

    def set_track_pan(self, track_num: int, value: float) -> None:
        """Set absolute track pan (0.0=L, 0.5=C, 1.0=R)."""
        value = max(0.0, min(1.0, value))
        self._send(f"/track/{track_num}/pan", value)

    def nudge_track_volume(self, track_num: int, current: float, increment: int) -> float:
        """Nudge track volume by encoder increment. Returns new value."""
        new_val = max(0.0, min(1.0, current + increment * VOLUME_STEP))
        self.set_track_volume(track_num, new_val)
        return new_val

    def nudge_track_pan(self, track_num: int, current: float, increment: int) -> float:
        """Nudge track pan by encoder increment. Returns new value."""
        new_val = max(0.0, min(1.0, current + increment * PAN_STEP))
        self.set_track_pan(track_num, new_val)
        return new_val

    # --- Track mute/solo/select ---

    def toggle_track_mute(self, track_num: int) -> None:
        self._send(f"/track/{track_num}/mute/toggle")

    def toggle_track_solo(self, track_num: int) -> None:
        self._send(f"/track/{track_num}/solo/toggle")

    def toggle_track_rec_arm(self, track_num: int) -> None:
        self._send(f"/track/{track_num}/recarm/toggle")

    def select_track(self, track_num: int, bank_size: int = 8) -> None:
        """Exclusively select a track (deselects all others in the bank)."""
        for i in range(1, bank_size + 1):
            if i != track_num:
                self._send(f"/track/{i}/select", 0)
        self._send(f"/track/{track_num}/select", 1)

    def select_and_arm_track(self, track_num: int, bank_size: int = 8) -> None:
        """Exclusively select and record-arm a track (disarms all others)."""
        for i in range(1, bank_size + 1):
            if i != track_num:
                self._send(f"/track/{i}/select", 0)
                self._send(f"/track/{i}/recarm", 0)
        self._send(f"/track/{track_num}/select", 1)
        self._send(f"/track/{track_num}/recarm", 1)

    def solo_reset(self) -> None:
        """Clear all solos."""
        self._send("/soloreset")

    # --- Master ---

    def set_master_volume(self, value: float) -> None:
        value = max(0.0, min(1.0, value))
        self._send("/master/volume", value)

    def nudge_master_volume(self, current: float, increment: int) -> float:
        new_val = max(0.0, min(1.0, current + increment * VOLUME_STEP))
        self.set_master_volume(new_val)
        return new_val

    # --- Bank navigation ---

    def next_track_bank(self) -> None:
        self._send("/device/track/bank/+")

    def prev_track_bank(self) -> None:
        self._send("/device/track/bank/-")

    def next_track(self) -> None:
        self._send("/device/track/+")

    def prev_track(self) -> None:
        self._send("/device/track/-")

    # --- Tempo ---

    def set_tempo(self, bpm: float) -> None:
        self._send("/tempo/raw", bpm)

    # --- MIDI note input (virtual keyboard) ---

    def note_on(self, channel: int, note: int, velocity: int) -> None:
        """Send MIDI note-on via Reaper's virtual keyboard OSC input."""
        self._send(f"/vkb_midi/{channel}/note/{note}", velocity)

    def note_off(self, channel: int, note: int) -> None:
        """Send MIDI note-off via Reaper's virtual keyboard OSC input."""
        self._send(f"/vkb_midi/{channel}/note/{note}", 0)

    # --- Send controls ---

    SEND_STEP = 0.015  # same sensitivity as volume

    def set_send_volume(self, track_num: int, send_idx: int, value: float) -> None:
        """Set send level (0.0-1.0). send_idx is 0-based."""
        value = max(0.0, min(1.0, value))
        self._send(f"/track/{track_num}/send/{send_idx + 1}/volume", value)

    def nudge_send_volume(self, track_num: int, send_idx: int,
                          current: float, increment: int) -> float:
        """Nudge send volume by encoder increment. Returns new value."""
        new_val = max(0.0, min(1.0, current + increment * self.SEND_STEP))
        self.set_send_volume(track_num, send_idx, new_val)
        return new_val

    def set_send_pan(self, track_num: int, send_idx: int, value: float) -> None:
        """Set send pan (0.0=L, 0.5=C, 1.0=R). send_idx is 0-based."""
        value = max(0.0, min(1.0, value))
        self._send(f"/track/{track_num}/send/{send_idx + 1}/pan", value)

    # --- Automation mode ---

    def set_track_automode(self, track_num: int, mode: int) -> None:
        """Set track automation mode (0=trim, 1=read, 2=touch, 3=write, 4=latch)."""
        self._send(f"/track/{track_num}/automode/{mode}")

    # --- FX / Device control ---

    def set_fx_param(self, track_num: int, fx_idx: int,
                     param_idx: int, value: float) -> None:
        """Set FX parameter value (0.0-1.0). Indices are 0-based."""
        value = max(0.0, min(1.0, value))
        self._send(f"/track/{track_num}/fx/{fx_idx + 1}/fxparam/{param_idx + 1}/value", value)

    def nudge_fx_param(self, track_num: int, fx_idx: int,
                       param_idx: int, current: float, increment: int) -> float:
        """Nudge FX parameter. Returns new value."""
        new_val = max(0.0, min(1.0, current + increment * 0.01))
        self.set_fx_param(track_num, fx_idx, param_idx, new_val)
        return new_val

    # --- Aftertouch / Pitch Bend ---

    def channel_pressure(self, channel: int, value: int) -> None:
        """Send channel aftertouch (0-127) via Reaper virtual keyboard."""
        self._send(f"/vkb_midi/{channel}/channelpressure", value)

    def poly_aftertouch(self, channel: int, note: int, value: int) -> None:
        """Send poly aftertouch for a specific note (0-127)."""
        self._send(f"/vkb_midi/{channel}/polyaftertouch/{note}", value)

    def pitch_bend(self, channel: int, value: float) -> None:
        """Send pitch bend (0.0-1.0, 0.5 = center) via Reaper virtual keyboard."""
        value = max(0.0, min(1.0, value))
        self._send(f"/vkb_midi/{channel}/pitch", value)

    # --- Actions ---

    def undo(self) -> None:
        """Trigger Reaper undo (action 40029)."""
        self._send("/action", 40029)

    def redo(self) -> None:
        """Trigger Reaper redo (action 40030)."""
        self._send("/action", 40030)

    def trigger_action(self, action_id: int) -> None:
        """Trigger a Reaper action by its command ID."""
        self._send("/action", action_id)
