"""Drum pad mode.

Bottom 4x4 pads (rows 4-7, cols 0-3) are mapped to 16 drum notes.
Top 4 rows show a 16-step grid for the selected drum pad.
Encoders can control drum pad parameters.
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

import push2_python.constants as c
from PIL import Image

from modes.base import Mode
from push2.buttons import UPPER_ROW, LOWER_ROW
from push2.encoders import EncoderManager, MASTER_ENCODER, TEMPO_ENCODER
from ui.drum_screen import DrumScreen

if TYPE_CHECKING:
    from main import Push2ReaperDaemon

log = logging.getLogger("push2reaper.modes.drum")

# Drum pad colors
COLOR_DRUM_PAD = "yellow"
COLOR_DRUM_SELECTED = "orange"
COLOR_STEP_ON = "green"
COLOR_STEP_OFF = "dark_gray"
COLOR_EMPTY = "black"


class DrumMode(Mode):
    """Drum pad mode with 4x4 drum pads and step sequencer grid."""

    name = "drum"

    def __init__(self):
        self._screen = DrumScreen()
        self._bank_offset = 36  # Starting MIDI note (GM drums start at 36)
        self._selected_pad = 0  # 0-15 within current bank
        # 16 steps for each of 16 pads
        self._step_grid: list[list[bool]] = [
            [False] * 16 for _ in range(16)
        ]
        self._held_notes: dict[tuple[int, int], int] = {}  # (row,col) → note

    def enter(self, daemon: Push2ReaperDaemon) -> None:
        log.info("Entering drum mode (bank %d-%d)",
                 self._bank_offset, self._bank_offset + 15)
        self._update_pad_colors(daemon)
        self._update_buttons(daemon)

    def exit(self, daemon: Push2ReaperDaemon) -> None:
        log.info("Exiting drum mode")
        # Invalidate PadManager's color cache so rebuild_grid actually repaints
        # (drum mode wrote colors directly, bypassing PadManager's dedup cache)
        if daemon.push2.pads:
            daemon.push2.pads.invalidate_cache()
            daemon.push2.pads.rebuild_grid()

    def on_button(self, daemon: Push2ReaperDaemon, button: str, name: str) -> bool:
        # Lower row: select tracks (same as mixer for consistency)
        if button in LOWER_ROW:
            idx = LOWER_ROW.index(button)
            track_num = daemon.state.bank_offset + 1 + idx
            daemon.osc_client.select_and_arm_track(track_num)
            log.info("→ Select track %d (drum mode)", track_num)
            return True

        # Upper row: could be used for drum bank navigation
        if button in UPPER_ROW:
            idx = UPPER_ROW.index(button)
            if idx == 0:
                # Bank down (lower 16 notes)
                self._bank_offset = max(0, self._bank_offset - 16)
                self._update_pad_colors(daemon)
                log.info("Drum bank down → %d-%d",
                         self._bank_offset, self._bank_offset + 15)
            elif idx == 1:
                # Bank up (higher 16 notes)
                self._bank_offset = min(112, self._bank_offset + 16)
                self._update_pad_colors(daemon)
                log.info("Drum bank up → %d-%d",
                         self._bank_offset, self._bank_offset + 15)
            return True

        return False

    def on_encoder(self, daemon: Push2ReaperDaemon, encoder: str, increment: int) -> None:
        # Master/tempo still work
        if encoder == MASTER_ENCODER:
            new_val = daemon.osc_client.nudge_master_volume(
                daemon.state.master_volume, increment
            )
            daemon.state.update_master(volume=new_val)
            return
        if encoder == TEMPO_ENCODER:
            new_tempo = max(20.0, min(300.0, daemon.state.tempo + increment))
            daemon.osc_client.set_tempo(new_tempo)
            return

        # Track encoders: could control drum pad volume/pan in the future
        track_idx = EncoderManager.get_track_index(encoder)
        if track_idx is not None:
            # For now, use encoders as track volume (like mixer)
            track_num = daemon.state.bank_offset + 1 + track_idx
            track = daemon.state.tracks.get(track_num)
            if track:
                new_val = daemon.osc_client.nudge_track_volume(
                    track_num, track.volume, increment
                )
                daemon.state.update_track(track_num, volume=new_val)

    def on_pad_pressed(self, daemon: Push2ReaperDaemon, row: int, col: int, velocity: int) -> None:
        if self._is_drum_pad(row, col):
            # Bottom 4x4: drum trigger
            pad_idx = self._drum_pad_index(row, col)
            note = self._bank_offset + pad_idx
            self._selected_pad = pad_idx
            self._held_notes[(row, col)] = note

            if daemon.push2.pads:
                daemon.push2.pads.highlight_pad(row, col)

            if 0 <= note <= 127:
                daemon.osc_client.note_on(9, note, velocity)  # Channel 10 for drums
                log.debug("Drum pad (%d,%d) vel=%d → note %d", row, col, velocity, note)

            self._update_pad_colors(daemon)

        elif self._is_step_pad(row, col):
            # Top 4 rows: step sequencer toggle
            step_idx = self._step_index(row, col)
            if step_idx is not None and step_idx < 16:
                self._step_grid[self._selected_pad][step_idx] = \
                    not self._step_grid[self._selected_pad][step_idx]
                self._update_pad_colors(daemon)
                log.debug("Step %d toggled for pad %d: %s",
                          step_idx, self._selected_pad,
                          self._step_grid[self._selected_pad][step_idx])

    def on_pad_released(self, daemon: Push2ReaperDaemon, row: int, col: int) -> None:
        if self._is_drum_pad(row, col):
            note = self._held_notes.pop((row, col), None)
            if note is not None and 0 <= note <= 127:
                daemon.osc_client.note_off(9, note)
            self._update_pad_colors(daemon)

    def on_aftertouch(self, daemon: Push2ReaperDaemon, row: int, col: int, value: int) -> None:
        if self._is_drum_pad(row, col):
            note = self._held_notes.get((row, col))
            if note is not None and 0 <= note <= 127:
                daemon.osc_client.poly_aftertouch(9, note, value)

    def on_state_changed(self, daemon: Push2ReaperDaemon, data: dict) -> None:
        if data.get("type") == "transport":
            if daemon.push2.buttons:
                daemon.push2.buttons.set_transport_state(
                    daemon.state.playing, daemon.state.recording
                )

    def render(self, daemon: Push2ReaperDaemon) -> Image.Image:
        steps = self._step_grid[self._selected_pad] if self._selected_pad < 16 else None
        return self._screen.render(self._selected_pad, self._bank_offset, steps)

    # --- Internal helpers ---

    @staticmethod
    def _is_drum_pad(row: int, col: int) -> bool:
        """Bottom 4x4 quadrant (rows 4-7, cols 0-3)."""
        return 4 <= row <= 7 and 0 <= col <= 3

    @staticmethod
    def _drum_pad_index(row: int, col: int) -> int:
        """Convert bottom 4x4 position to pad index 0-15."""
        return (7 - row) * 4 + col

    @staticmethod
    def _is_step_pad(row: int, col: int) -> bool:
        """Top 4 rows used for step grid (rows 0-3, all cols) or
        rows 4-7 cols 4-7."""
        return row <= 3 or (4 <= row <= 7 and 4 <= col <= 7)

    @staticmethod
    def _step_index(row: int, col: int) -> int | None:
        """Convert step pad position to step index 0-15."""
        if row <= 1:
            # Rows 0-1: steps 0-15 (2 rows x 8 cols)
            return (1 - row) * 8 + col
        return None

    def _update_pad_colors(self, daemon: Push2ReaperDaemon) -> None:
        """Update all pad colors for drum mode."""
        if not daemon.push2.pads:
            return

        push = daemon.push2.pads._push

        for row in range(8):
            for col in range(8):
                if self._is_drum_pad(row, col):
                    pad_idx = self._drum_pad_index(row, col)
                    if pad_idx == self._selected_pad:
                        color = COLOR_DRUM_SELECTED
                    else:
                        color = COLOR_DRUM_PAD
                    push.pads.set_pad_color((row, col), color)
                elif row <= 1:
                    # Step grid rows
                    step_idx = self._step_index(row, col)
                    if step_idx is not None and step_idx < 16:
                        if self._step_grid[self._selected_pad][step_idx]:
                            color = COLOR_STEP_ON
                        else:
                            color = COLOR_STEP_OFF
                        push.pads.set_pad_color((row, col), color)
                    else:
                        push.pads.set_pad_color((row, col), COLOR_EMPTY)
                else:
                    push.pads.set_pad_color((row, col), COLOR_EMPTY)

    def _update_buttons(self, daemon: Push2ReaperDaemon) -> None:
        if not daemon.push2.buttons:
            return
        # Upper row: first two for bank nav
        for i, btn in enumerate(UPPER_ROW):
            if i == 0:
                daemon.push2.buttons.set_color(btn, "blue")  # bank down
            elif i == 1:
                daemon.push2.buttons.set_color(btn, "blue")  # bank up
            else:
                daemon.push2.buttons.set_color(btn, "dark_gray")
        for btn in LOWER_ROW:
            daemon.push2.buttons.set_color(btn, "dark_gray")
