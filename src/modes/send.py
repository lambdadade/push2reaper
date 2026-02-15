"""Send controls mode.

Encoders 1-8 control send levels for the currently selected track.
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

import push2_python.constants as c
from PIL import Image

from modes.base import Mode
from push2.buttons import UPPER_ROW, LOWER_ROW
from push2.encoders import EncoderManager, MASTER_ENCODER, TEMPO_ENCODER
from ui.send_screen import SendScreen

if TYPE_CHECKING:
    from main import Push2ReaperDaemon

log = logging.getLogger("push2reaper.modes.send")


class SendMode(Mode):
    """Send levels mode — encoders control sends for the selected track."""

    name = "send"

    def __init__(self):
        self._screen = SendScreen()

    def enter(self, daemon: Push2ReaperDaemon) -> None:
        log.info("Entering send mode")
        self._update_buttons(daemon)

    def exit(self, daemon: Push2ReaperDaemon) -> None:
        log.info("Exiting send mode")

    def on_button(self, daemon: Push2ReaperDaemon, button: str, name: str) -> bool:
        # Lower row: select track (same as mixer)
        if button in LOWER_ROW:
            idx = LOWER_ROW.index(button)
            track_num = daemon.state.bank_offset + 1 + idx
            daemon.osc_client.select_and_arm_track(track_num)
            log.info("→ Select track %d (send mode)", track_num)
            return True
        return False

    def on_encoder(self, daemon: Push2ReaperDaemon, encoder: str, increment: int) -> None:
        # Track encoders control sends for the selected track
        send_idx = EncoderManager.get_track_index(encoder)
        if send_idx is not None:
            track_num = daemon.state.selected_track
            track = daemon.state.tracks.get(track_num)
            if track is None:
                return
            # Ensure send exists in state
            while len(track.sends) <= send_idx:
                track.sends.append({
                    "name": f"Send {len(track.sends) + 1}",
                    "volume": 0.0, "volume_str": "-inf dB", "pan": 0.5,
                })
            current = track.sends[send_idx].get("volume", 0.0)
            new_val = daemon.osc_client.nudge_send_volume(
                track_num, send_idx, current, increment
            )
            daemon.state.update_send(track_num, send_idx, volume=new_val)
            return

        # Master/tempo encoders still work globally
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
        # Pads still play notes in send mode
        if daemon.push2.pads:
            daemon.push2.pads.highlight_pad(row, col)
        virtual_note = daemon.scale_state.pad_note(row, col)
        if 0 <= virtual_note <= 127:
            daemon.osc_client.note_on(0, virtual_note, velocity)

    def on_pad_released(self, daemon: Push2ReaperDaemon, row: int, col: int) -> None:
        if daemon.push2.pads:
            daemon.push2.pads.restore_pad(row, col)
        virtual_note = daemon.scale_state.pad_note(row, col)
        if 0 <= virtual_note <= 127:
            daemon.osc_client.note_off(0, virtual_note)

    def on_aftertouch(self, daemon: Push2ReaperDaemon, row: int, col: int, value: int) -> None:
        virtual_note = daemon.scale_state.pad_note(row, col)
        if 0 <= virtual_note <= 127:
            daemon.osc_client.poly_aftertouch(0, virtual_note, value)

    def on_state_changed(self, daemon: Push2ReaperDaemon, data: dict) -> None:
        if data.get("type") == "transport":
            if daemon.push2.buttons:
                daemon.push2.buttons.set_transport_state(
                    daemon.state.playing, daemon.state.recording
                )

    def render(self, daemon: Push2ReaperDaemon) -> Image.Image:
        return self._screen.render(daemon.state)

    def _update_buttons(self, daemon: Push2ReaperDaemon) -> None:
        if not daemon.push2.buttons:
            return
        for btn in UPPER_ROW:
            daemon.push2.buttons.set_color(btn, "dark_gray")
        for i, btn in enumerate(LOWER_ROW):
            track_num = daemon.state.bank_offset + 1 + i
            track = daemon.state.tracks.get(track_num)
            if track and track.selected:
                daemon.push2.buttons.set_color(btn, "white")
            else:
                daemon.push2.buttons.set_color(btn, "dark_gray")
