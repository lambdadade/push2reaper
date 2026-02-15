"""Session/clip launching mode.

Pad grid maps to clip slots (8 tracks x 8 scenes).
Designed to work with Helgoboss Playtime via ReaLearn MIDI targets.

Playtime integration: This mode sends MIDI notes on a dedicated channel
that ReaLearn can map to Playtime's slot/row/column targets. The user
configures ReaLearn mappings to connect these MIDI messages to Playtime
clip triggering.

Default mapping scheme:
- Pad press: note_on on channel 15 (MIDI ch 16), note = row*8 + col
  → Map in ReaLearn to "Slot management action" (trigger/record)
- Scene buttons (right column, row 0-7 pad col 7): trigger full scene
  → Map to "Row action" (trigger)
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

import push2_python.constants as c
from PIL import Image

from modes.base import Mode
from push2.buttons import UPPER_ROW, LOWER_ROW
from push2.encoders import EncoderManager, MASTER_ENCODER, TEMPO_ENCODER
from ui.session_screen import SessionScreen

if TYPE_CHECKING:
    from main import Push2ReaperDaemon

log = logging.getLogger("push2reaper.modes.session")

# MIDI channel for Playtime control (0-indexed, so 15 = MIDI ch 16)
PLAYTIME_CHANNEL = 15

# Pad colors for clip states
CLIP_COLORS = {
    0: "dark_gray",   # empty
    1: "white",       # has content (stopped)
    2: "green",       # playing
    3: "red",         # recording
    4: "yellow",      # queued
}


class SessionMode(Mode):
    """Session/clip launcher mode for Playtime integration."""

    name = "session"

    def __init__(self):
        self._screen = SessionScreen()
        self._scene_offset = 0  # First visible scene row
        # 8x8 clip state grid (0=empty, 1=stopped, 2=playing, 3=rec, 4=queued)
        self._clip_states: list[list[int]] = [
            [0] * 8 for _ in range(8)
        ]

    def enter(self, daemon: Push2ReaperDaemon) -> None:
        log.info("Entering session mode (scenes %d-%d)",
                 self._scene_offset + 1, self._scene_offset + 8)
        self._update_pad_colors(daemon)
        self._update_buttons(daemon)

    def exit(self, daemon: Push2ReaperDaemon) -> None:
        log.info("Exiting session mode")
        if daemon.push2.pads:
            daemon.push2.pads.invalidate_cache()
            daemon.push2.pads.rebuild_grid()

    def on_button(self, daemon: Push2ReaperDaemon, button: str, name: str) -> bool:
        # Upper row: scene navigation
        if button in UPPER_ROW:
            idx = UPPER_ROW.index(button)
            if idx == 0:
                self._scene_offset = max(0, self._scene_offset - 8)
                self._update_pad_colors(daemon)
                log.info("Scene bank ← %d-%d",
                         self._scene_offset + 1, self._scene_offset + 8)
            elif idx == 1:
                self._scene_offset += 8
                self._update_pad_colors(daemon)
                log.info("Scene bank → %d-%d",
                         self._scene_offset + 1, self._scene_offset + 8)
            return True

        # Lower row: stop clips on track
        if button in LOWER_ROW:
            idx = LOWER_ROW.index(button)
            # Send a stop-clip signal for the track column
            # Using note_off on Playtime channel as "stop" signal
            track_num = daemon.state.bank_offset + 1 + idx
            daemon.osc_client.note_on(PLAYTIME_CHANNEL, 120 + idx, 127)
            daemon.osc_client.note_off(PLAYTIME_CHANNEL, 120 + idx)
            log.info("→ Stop clips track %d", track_num)
            return True

        return False

    def on_encoder(self, daemon: Push2ReaperDaemon, encoder: str, increment: int) -> None:
        # Encoders control track volume in session mode
        track_idx = EncoderManager.get_track_index(encoder)
        if track_idx is not None:
            track_num = daemon.state.bank_offset + 1 + track_idx
            track = daemon.state.tracks.get(track_num)
            if track:
                new_val = daemon.osc_client.nudge_track_volume(
                    track_num, track.volume, increment
                )
                daemon.state.update_track(track_num, volume=new_val)
            return

        if encoder == MASTER_ENCODER:
            new_val = daemon.osc_client.nudge_master_volume(
                daemon.state.master_volume, increment
            )
            daemon.state.update_master(volume=new_val)
            return
        if encoder == TEMPO_ENCODER:
            new_tempo = max(20.0, min(300.0, daemon.state.tempo + increment))
            daemon.osc_client.set_tempo(new_tempo)

    def on_pad_pressed(self, daemon: Push2ReaperDaemon, row: int, col: int, velocity: int) -> None:
        # Map pad to clip slot trigger
        # Note number encodes position: row * 8 + col
        # Sent on Playtime channel for ReaLearn to pick up
        note = row * 8 + col
        daemon.osc_client.note_on(PLAYTIME_CHANNEL, note, velocity)
        log.info("Session pad (%d,%d) → clip trigger note %d", row, col, note)

        if daemon.push2.pads:
            daemon.push2.pads.highlight_pad(row, col)

    def on_pad_released(self, daemon: Push2ReaperDaemon, row: int, col: int) -> None:
        note = row * 8 + col
        daemon.osc_client.note_off(PLAYTIME_CHANNEL, note)
        self._update_pad_colors(daemon)

    def on_state_changed(self, daemon: Push2ReaperDaemon, data: dict) -> None:
        if data.get("type") == "transport":
            if daemon.push2.buttons:
                daemon.push2.buttons.set_transport_state(
                    daemon.state.playing, daemon.state.recording
                )

    def render(self, daemon: Push2ReaperDaemon) -> Image.Image:
        tracks = daemon.state.get_bank_tracks()
        track_names = [t.name for t in tracks]
        return self._screen.render(track_names, self._scene_offset,
                                   self._clip_states)

    def _update_pad_colors(self, daemon: Push2ReaperDaemon) -> None:
        """Update pad colors based on clip states."""
        if not daemon.push2.pads:
            return
        push = daemon.push2.pads._push
        for row in range(8):
            for col in range(8):
                state = 0
                if row < len(self._clip_states) and col < len(self._clip_states[row]):
                    state = self._clip_states[row][col]
                color = CLIP_COLORS.get(state, "dark_gray")
                push.pads.set_pad_color((row, col), color)

    def _update_buttons(self, daemon: Push2ReaperDaemon) -> None:
        if not daemon.push2.buttons:
            return
        # Upper row: scene navigation
        for i, btn in enumerate(UPPER_ROW):
            if i in (0, 1):
                daemon.push2.buttons.set_color(btn, "blue")
            else:
                daemon.push2.buttons.set_color(btn, "dark_gray")
        # Lower row: stop buttons (red)
        for btn in LOWER_ROW:
            daemon.push2.buttons.set_color(btn, "red")
