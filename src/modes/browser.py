"""Browser mode.

Provides FX/preset browsing via Reaper actions. Since Reaper's OSC
doesn't expose rich browser navigation, this mode uses action IDs
to open/navigate the FX browser and related windows.

Key Reaper actions used:
- 40271: Show FX browser
- 40291: Show FX chain for selected track
- 40346: Show track insert dialog
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

import push2_python.constants as c
from PIL import Image

from modes.base import Mode
from push2.buttons import UPPER_ROW, LOWER_ROW
from push2.encoders import EncoderManager, MASTER_ENCODER, TEMPO_ENCODER
from ui.browser_screen import BrowserScreen

if TYPE_CHECKING:
    from main import Push2ReaperDaemon

log = logging.getLogger("push2reaper.modes.browser")

# Reaper action IDs for browser operations
ACTION_FX_BROWSER = 40271       # Show FX browser window
ACTION_FX_CHAIN = 40291         # View FX chain for current/last touched track
ACTION_INSERT_VIRTUAL_INSTRUMENT = 40346  # Track: Insert virtual instrument


class BrowserMode(Mode):
    """FX/preset browser mode using Reaper actions."""

    name = "browser"

    def __init__(self):
        self._screen = BrowserScreen()

    def enter(self, daemon: Push2ReaperDaemon) -> None:
        log.info("Entering browser mode")
        # Auto-open the FX browser when entering browser mode
        daemon.osc_client.trigger_action(ACTION_FX_BROWSER)
        self._update_buttons(daemon)

    def exit(self, daemon: Push2ReaperDaemon) -> None:
        log.info("Exiting browser mode")

    def on_button(self, daemon: Push2ReaperDaemon, button: str, name: str) -> bool:
        if button in UPPER_ROW:
            idx = UPPER_ROW.index(button)
            if idx == 0:
                daemon.osc_client.trigger_action(ACTION_FX_BROWSER)
                log.info("→ Open FX browser")
            elif idx == 1:
                daemon.osc_client.trigger_action(ACTION_FX_CHAIN)
                log.info("→ Open FX chain")
            elif idx == 2:
                daemon.osc_client.trigger_action(ACTION_INSERT_VIRTUAL_INSTRUMENT)
                log.info("→ Insert virtual instrument")
            return True

        # Lower row: select track
        if button in LOWER_ROW:
            idx = LOWER_ROW.index(button)
            track_num = daemon.state.bank_offset + 1 + idx
            daemon.osc_client.select_and_arm_track(track_num)
            log.info("→ Select track %d (browser mode)", track_num)
            return True

        return False

    def on_encoder(self, daemon: Push2ReaperDaemon, encoder: str, increment: int) -> None:
        # Master/tempo encoders work normally
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

        # Track encoders: could be used for navigating within the browser
        # For now, encoder 1 sends keyboard-like navigation actions
        track_idx = EncoderManager.get_track_index(encoder)
        if track_idx == 0:
            # First encoder: navigate FX/preset list
            if increment > 0:
                # Next item (Down arrow equivalent)
                daemon.osc_client.trigger_action(40001)  # Transport: Play (placeholder)
                log.debug("Browser nav: next (%+d)", increment)
            else:
                log.debug("Browser nav: prev (%+d)", increment)

    def on_pad_pressed(self, daemon: Push2ReaperDaemon, row: int, col: int, velocity: int) -> None:
        # Pads still play notes in browser mode
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

    def on_state_changed(self, daemon: Push2ReaperDaemon, data: dict) -> None:
        if data.get("type") == "transport":
            if daemon.push2.buttons:
                daemon.push2.buttons.set_transport_state(
                    daemon.state.playing, daemon.state.recording
                )

    def render(self, daemon: Push2ReaperDaemon) -> Image.Image:
        track = daemon.state.tracks.get(daemon.state.selected_track)
        track_name = track.name if track else "?"
        return self._screen.render(track_name)

    def _update_buttons(self, daemon: Push2ReaperDaemon) -> None:
        if not daemon.push2.buttons:
            return
        for i, btn in enumerate(UPPER_ROW):
            if i < 3:
                daemon.push2.buttons.set_color(btn, "orange")
            else:
                daemon.push2.buttons.set_color(btn, "dark_gray")
        for btn in LOWER_ROW:
            daemon.push2.buttons.set_color(btn, "dark_gray")
