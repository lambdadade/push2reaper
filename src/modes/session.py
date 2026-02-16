"""Session/clip launching mode.

Uses Playtime's gRPC API directly (via PlaytimeClient) for clip control
and real-time state feedback. No ReaLearn/MIDI bridging required.

Pad grid maps to Playtime clip slots (columns x scenes).
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

import push2_python.constants as c
from PIL import Image

from modes.base import Mode
from push2.buttons import UPPER_ROW, LOWER_ROW
from push2.encoders import EncoderManager, MASTER_ENCODER, TEMPO_ENCODER
from playtime.client import (
    PlaytimeClient, SLOT_EMPTY, SLOT_STOPPED, SLOT_PLAYING,
    SLOT_RECORDING, SLOT_QUEUED,
)
from ui.session_screen import SessionScreen

if TYPE_CHECKING:
    from main import Push2ReaperDaemon

log = logging.getLogger("push2reaper.modes.session")

# Pad colors for clip states
PAD_COLORS = {
    SLOT_EMPTY: "dark_gray",
    SLOT_STOPPED: "white",
    SLOT_PLAYING: "green",
    SLOT_RECORDING: "red",
    SLOT_QUEUED: "yellow",
}


class SessionMode(Mode):
    """Session/clip launcher mode using Playtime gRPC."""

    name = "session"

    def __init__(self):
        self._screen = SessionScreen()
        self._scene_offset = 0  # First visible scene row
        self._daemon = None  # Set during enter(), used for streaming callbacks

    def enter(self, daemon: Push2ReaperDaemon) -> None:
        log.info("Entering session mode (scenes %d-%d)",
                 self._scene_offset + 1, self._scene_offset + 8)
        self._daemon = daemon
        # Subscribe to playtime state changes for real-time pad updates
        daemon.event_bus.subscribe("playtime_state_changed",
                                   self._on_playtime_changed)
        self._update_pad_colors(daemon)
        self._update_buttons(daemon)

    def exit(self, daemon: Push2ReaperDaemon) -> None:
        log.info("Exiting session mode")
        self._daemon = None
        daemon.event_bus.unsubscribe("playtime_state_changed",
                                      self._on_playtime_changed)
        if daemon.push2.pads:
            daemon.push2.pads.invalidate_cache()
            daemon.push2.pads.rebuild_grid()

    def on_button(self, daemon: Push2ReaperDaemon, button: str, name: str) -> bool:
        # Upper row: scene navigation (first 2) + scene trigger (rest)
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
            else:
                # Scene trigger buttons (upper row positions 2-7)
                scene = self._scene_offset + (idx - 2)
                daemon.playtime.trigger_scene(scene)
                log.info("→ Trigger scene %d", scene + 1)
            return True

        # Lower row: stop clips on track
        if button in LOWER_ROW:
            idx = LOWER_ROW.index(button)
            daemon.playtime.stop_column(idx)
            log.info("→ Stop column %d", idx)
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
        # Map pad grid position to Playtime slot
        # Pads: row 0 = top, row 7 = bottom; col 0 = left, col 7 = right
        # Playtime: column = track, row = scene
        pt_col = col
        pt_row = row + self._scene_offset

        daemon.playtime.trigger_slot(pt_col, pt_row)
        log.info("Session pad (%d,%d) → trigger slot [col=%d, row=%d]",
                 row, col, pt_col, pt_row)

        if daemon.push2.pads:
            daemon.push2.pads.highlight_pad(row, col)

    def on_pad_released(self, daemon: Push2ReaperDaemon, row: int, col: int) -> None:
        self._update_pad_colors(daemon)

    def on_state_changed(self, daemon: Push2ReaperDaemon, data: dict) -> None:
        if data.get("type") == "transport":
            if daemon.push2.buttons:
                daemon.push2.buttons.set_transport_state(
                    daemon.state.playing, daemon.state.recording
                )

    def render(self, daemon: Push2ReaperDaemon) -> Image.Image:
        # Get clip states from Playtime client
        pt = daemon.playtime
        clip_states = pt.get_grid_state(
            num_cols=8, num_rows=8,
            col_offset=0, row_offset=self._scene_offset,
        )

        # Get column names from Playtime
        track_names = []
        for i in range(8):
            name = pt.column_names.get(i, "")
            if not name and not pt.is_connected:
                # Fall back to Reaper track names if not connected
                reaper_tracks = daemon.state.get_bank_tracks()
                name = reaper_tracks[i].name if i < len(reaper_tracks) else ""
            track_names.append(name)

        return self._screen.render(
            track_names, self._scene_offset, clip_states,
            connected=pt.is_connected,
            num_columns=pt.num_columns,
            num_rows=pt.num_rows,
        )

    def _on_playtime_changed(self, data: dict) -> None:
        """Called when Playtime state changes (from streaming thread)."""
        # Update pad colors in real-time when clip states change
        if self._daemon is not None:
            try:
                self._update_pad_colors(self._daemon)
            except Exception:
                pass  # Don't crash the streaming thread

    def _update_pad_colors(self, daemon: Push2ReaperDaemon) -> None:
        """Update pad colors based on Playtime clip states."""
        if not daemon.push2.pads:
            return
        push = daemon.push2.pads._push
        pt = daemon.playtime
        grid = pt.get_grid_state(
            num_cols=8, num_rows=8,
            col_offset=0, row_offset=self._scene_offset,
        )
        for row in range(8):
            for col in range(8):
                state = grid[row][col] if row < len(grid) and col < len(grid[row]) else SLOT_EMPTY
                color = PAD_COLORS.get(state, "dark_gray")
                push.pads.set_pad_color((row, col), color)

    def _update_buttons(self, daemon: Push2ReaperDaemon) -> None:
        if not daemon.push2.buttons:
            return
        # Upper row: scene nav (blue) + scene triggers (orange)
        for i, btn in enumerate(UPPER_ROW):
            if i in (0, 1):
                daemon.push2.buttons.set_color(btn, "blue")
            else:
                daemon.push2.buttons.set_color(btn, "orange")
        # Lower row: stop buttons (red)
        for btn in LOWER_ROW:
            daemon.push2.buttons.set_color(btn, "red")
