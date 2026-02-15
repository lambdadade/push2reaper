"""Mixer mode — default operating mode.

Handles volume/pan encoders, mute/solo/select lower row, and renders
the mixer screen with 8 channel strips.
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

import push2_python.constants as c
from PIL import Image

from modes.base import Mode
from push2.buttons import UPPER_ROW, LOWER_ROW
from push2.encoders import EncoderManager, MASTER_ENCODER, TEMPO_ENCODER
from ui.screens import MixerScreen
from ui.send_screen import SendScreen

if TYPE_CHECKING:
    from main import Push2ReaperDaemon

log = logging.getLogger("push2reaper.modes.mixer")


class MixerMode(Mode):
    """Default mixer mode with volume/pan encoders and mute/solo/select."""

    name = "mixer"

    ENCODER_MODES = ["volume", "pan", "send"]

    def __init__(self):
        self._encoder_mode = "volume"  # "volume", "pan", or "send"
        self._lower_row_mode = "select"  # "select", "mute", "solo"
        self._mixer_screen = MixerScreen()
        self._send_screen = SendScreen()

    def enter(self, daemon: Push2ReaperDaemon) -> None:
        log.info("Entering mixer mode")
        self._update_mode_buttons(daemon)

    def exit(self, daemon: Push2ReaperDaemon) -> None:
        log.info("Exiting mixer mode")

    def on_button(self, daemon: Push2ReaperDaemon, button: str, name: str) -> bool:
        # Mode buttons: Mute/Solo toggle for lower row
        if button == c.BUTTON_MUTE:
            self._lower_row_mode = "mute" if self._lower_row_mode != "mute" else "select"
            self._update_mode_buttons(daemon)
            log.info("Lower row mode: %s", self._lower_row_mode)
            return True

        if button == c.BUTTON_SOLO:
            self._lower_row_mode = "solo" if self._lower_row_mode != "solo" else "select"
            self._update_mode_buttons(daemon)
            log.info("Lower row mode: %s", self._lower_row_mode)
            return True

        # Lower row buttons (1-8): mute/solo/select depending on mode
        if button in LOWER_ROW:
            idx = LOWER_ROW.index(button)
            track_num = daemon.state.bank_offset + 1 + idx
            if self._lower_row_mode == "mute":
                daemon.osc_client.toggle_track_mute(track_num)
                log.info("→ Toggle mute track %d", track_num)
            elif self._lower_row_mode == "solo":
                daemon.osc_client.toggle_track_solo(track_num)
                log.info("→ Toggle solo track %d", track_num)
            else:
                daemon.osc_client.select_and_arm_track(track_num)
                log.info("→ Select + arm track %d", track_num)
            return True

        # Upper row buttons: cycle encoder mode (volume/pan/send)
        if button in UPPER_ROW:
            modes = self.ENCODER_MODES
            idx = modes.index(self._encoder_mode) if self._encoder_mode in modes else 0
            self._encoder_mode = modes[(idx + 1) % len(modes)]
            self._update_mode_buttons(daemon)
            log.info("Encoder mode: %s", self._encoder_mode)
            return True

        return False

    def on_encoder(self, daemon: Push2ReaperDaemon, encoder: str, increment: int) -> None:
        # Track encoders (1-8)
        track_idx = EncoderManager.get_track_index(encoder)
        if track_idx is not None:
            if self._encoder_mode == "send":
                # In send mode, encoders control sends for the selected track
                track_num = daemon.state.selected_track
                track = daemon.state.tracks.get(track_num)
                if track is None:
                    return
                send_idx = track_idx
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
            else:
                track_num = daemon.state.bank_offset + 1 + track_idx
                track = daemon.state.tracks.get(track_num)
                if track is None:
                    return
                if self._encoder_mode == "volume":
                    new_val = daemon.osc_client.nudge_track_volume(
                        track_num, track.volume, increment
                    )
                    daemon.state.update_track(track_num, volume=new_val)
                elif self._encoder_mode == "pan":
                    new_val = daemon.osc_client.nudge_track_pan(
                        track_num, track.pan, increment
                    )
                    daemon.state.update_track(track_num, pan=new_val)
            return

        # Master encoder
        if encoder == MASTER_ENCODER:
            new_val = daemon.osc_client.nudge_master_volume(
                daemon.state.master_volume, increment
            )
            daemon.state.update_master(volume=new_val)
            return

        # Tempo encoder
        if encoder == TEMPO_ENCODER:
            new_tempo = max(20.0, min(300.0, daemon.state.tempo + increment))
            daemon.osc_client.set_tempo(new_tempo)
            return

    def on_pad_pressed(self, daemon: Push2ReaperDaemon, row: int, col: int, velocity: int) -> None:
        if daemon.push2.pads:
            daemon.push2.pads.highlight_pad(row, col)

        virtual_note = daemon.scale_state.pad_note(row, col)
        if 0 <= virtual_note <= 127:
            daemon.osc_client.note_on(0, virtual_note, velocity)
            log.debug("Pad (%d,%d) vel=%d → note %d", row, col, velocity, virtual_note)

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
        if data and data.get("type") == "transport":
            if daemon.push2.buttons:
                daemon.push2.buttons.set_transport_state(
                    daemon.state.playing, daemon.state.recording
                )

    def render(self, daemon: Push2ReaperDaemon) -> Image.Image:
        if self._encoder_mode == "send":
            return self._send_screen.render(daemon.state)
        return self._mixer_screen.render(daemon.state)

    def _update_mode_buttons(self, daemon: Push2ReaperDaemon) -> None:
        """Update button LEDs to reflect current mode."""
        if not daemon.push2.buttons:
            return

        # Mute/Solo mode indicators
        daemon.push2.buttons.set_color(
            c.BUTTON_MUTE,
            "red" if self._lower_row_mode == "mute" else "dark_gray",
        )
        daemon.push2.buttons.set_color(
            c.BUTTON_SOLO,
            "yellow" if self._lower_row_mode == "solo" else "dark_gray",
        )

        # Lower row button colors based on mode
        for i, btn in enumerate(LOWER_ROW):
            track_num = daemon.state.bank_offset + 1 + i
            track = daemon.state.tracks.get(track_num)
            if track is None:
                continue
            if self._lower_row_mode == "mute":
                color = "red" if track.mute else "dark_gray"
            elif self._lower_row_mode == "solo":
                color = "yellow" if track.solo else "dark_gray"
            else:
                color = "white" if track.selected else "dark_gray"
            daemon.push2.buttons.set_color(btn, color)

        # Restore upper row to default
        for btn in UPPER_ROW:
            daemon.push2.buttons.set_color(btn, "dark_gray")
