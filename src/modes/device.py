"""Device/plugin control mode.

Encoders 1-8 map to FX parameters for the selected track's current FX.
Page left/right navigates FX chain, upper row cycles parameter banks.
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

import push2_python.constants as c
from PIL import Image

from modes.base import Mode
from push2.buttons import UPPER_ROW, LOWER_ROW
from push2.encoders import EncoderManager, MASTER_ENCODER, TEMPO_ENCODER
from ui.device_screen import DeviceScreen

if TYPE_CHECKING:
    from main import Push2ReaperDaemon

log = logging.getLogger("push2reaper.modes.device")


class DeviceMode(Mode):
    """Device/FX parameter control mode."""

    name = "device"

    def __init__(self):
        self._screen = DeviceScreen()
        self._fx_idx = 0        # Current FX index (0-based)
        self._param_bank = 0    # Current parameter bank (0-based, 8 per bank)

    def enter(self, daemon: Push2ReaperDaemon) -> None:
        log.info("Entering device mode (FX %d, param bank %d)",
                 self._fx_idx, self._param_bank)
        self._update_buttons(daemon)

    def exit(self, daemon: Push2ReaperDaemon) -> None:
        log.info("Exiting device mode")

    def on_button(self, daemon: Push2ReaperDaemon, button: str, name: str) -> bool:
        # Upper row: navigate parameter banks
        if button in UPPER_ROW:
            idx = UPPER_ROW.index(button)
            if idx == 0:
                # Previous param bank
                self._param_bank = max(0, self._param_bank - 1)
                log.info("Param bank ← %d", self._param_bank)
            elif idx == 1:
                # Next param bank
                self._param_bank += 1
                log.info("Param bank → %d", self._param_bank)
            elif idx == 6:
                # Previous FX in chain
                self._fx_idx = max(0, self._fx_idx - 1)
                self._param_bank = 0
                log.info("FX ← %d", self._fx_idx)
            elif idx == 7:
                # Next FX in chain
                self._fx_idx += 1
                self._param_bank = 0
                log.info("FX → %d", self._fx_idx)
            self._update_buttons(daemon)
            return True

        # Lower row: select track
        if button in LOWER_ROW:
            idx = LOWER_ROW.index(button)
            track_num = daemon.state.bank_offset + 1 + idx
            daemon.osc_client.select_and_arm_track(track_num)
            self._fx_idx = 0
            self._param_bank = 0
            log.info("→ Select track %d (device mode)", track_num)
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

        # Track encoders → FX parameters
        encoder_idx = EncoderManager.get_track_index(encoder)
        if encoder_idx is not None:
            track_num = daemon.state.selected_track
            param_idx = self._param_bank * 8 + encoder_idx

            # Get current value from state
            fx_list = daemon.state.fx.get(track_num, [])
            if self._fx_idx < len(fx_list):
                fx = fx_list[self._fx_idx]
                if param_idx < len(fx.params):
                    current = fx.params[param_idx].get("value", 0.0)
                else:
                    current = 0.0
            else:
                current = 0.0

            new_val = daemon.osc_client.nudge_fx_param(
                track_num, self._fx_idx, param_idx, current, increment
            )
            daemon.state.update_fx_param(
                track_num, self._fx_idx, param_idx, value=new_val
            )

    def on_pad_pressed(self, daemon: Push2ReaperDaemon, row: int, col: int, velocity: int) -> None:
        # Pads still play notes in device mode
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
        return self._screen.render(
            daemon.state, daemon.state.selected_track,
            self._fx_idx, self._param_bank
        )

    def _update_buttons(self, daemon: Push2ReaperDaemon) -> None:
        if not daemon.push2.buttons:
            return
        # Upper row: param bank nav (0,1) and FX nav (6,7)
        for i, btn in enumerate(UPPER_ROW):
            if i in (0, 1):
                daemon.push2.buttons.set_color(btn, "blue")
            elif i in (6, 7):
                daemon.push2.buttons.set_color(btn, "orange")
            else:
                daemon.push2.buttons.set_color(btn, "dark_gray")
        # Lower row: track select
        for i, btn in enumerate(LOWER_ROW):
            track_num = daemon.state.bank_offset + 1 + i
            track = daemon.state.tracks.get(track_num)
            if track and track.selected:
                daemon.push2.buttons.set_color(btn, "white")
            else:
                daemon.push2.buttons.set_color(btn, "dark_gray")
