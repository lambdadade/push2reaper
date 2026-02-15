#!/usr/bin/env python3
"""Push 2 Reaper Controller — main entry point.

Runs an asyncio event loop that:
  1. Connects to Push 2 hardware (MIDI + display)
  2. Starts OSC server for Reaper feedback
  3. Routes Push 2 input to Reaper via OSC
  4. Renders display at 30 fps via the active Mode
"""

import asyncio
import signal
import sys
import os
import logging

# Add src/ to path so imports work when running directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config
from core.logging_config import setup_logging
from core.event_bus import EventBus
from push2.hardware import Push2Hardware
from push2.scales import ScaleState
from push2.buttons import BUTTON_NAME_LOOKUP
from reaper.osc_client import ReaperOSCClient
from reaper.osc_server import ReaperOSCServer
from reaper.state import ReaperState
from modes.base import Mode
from modes.mixer import MixerMode
from modes.scale import ScaleMode
from modes.drum import DrumMode
from modes.device import DeviceMode
from modes.session import SessionMode
from modes.browser import BrowserMode

import push2_python.constants as c

log = logging.getLogger("push2reaper.main")


class Push2ReaperDaemon:
    """Main application daemon."""

    def __init__(self, config: dict):
        self.config = config
        self.event_bus = EventBus()
        self._running = False
        self._fps = config.get("push2", {}).get("fps", 30)

        # Shift state
        self._shift_held = False

        # Scale state (shared between PadManager and modes)
        self.scale_state = ScaleState()

        # Reaper state
        self.state = ReaperState(event_bus=self.event_bus)

        # OSC communication
        osc_cfg = config.get("osc", {})
        self.osc_client = ReaperOSCClient(
            ip=osc_cfg.get("reaper_ip", "127.0.0.1"),
            port=osc_cfg.get("reaper_port", 8000),
        )
        self.osc_server = ReaperOSCServer(
            port=osc_cfg.get("listen_port", 9000),
            state=self.state,
        )

        # Push 2 hardware
        self.push2 = Push2Hardware(self.event_bus, config,
                                   scale_state=self.scale_state)

        # Mode system
        self._mixer_mode = MixerMode()
        self._scale_mode = ScaleMode()
        self._drum_mode = DrumMode()
        self._device_mode = DeviceMode()
        self._session_mode = SessionMode()
        self._browser_mode = BrowserMode()
        self._mode: Mode = self._mixer_mode
        self._previous_mode: Mode | None = None  # for overlay modes like scale

        self._setup_event_handlers()

    # --- Mode switching ---

    def switch_mode(self, new_mode: Mode) -> None:
        """Switch to a new mode, calling exit/enter lifecycle methods."""
        if new_mode is self._mode:
            return
        self._mode.exit(self)
        self._mode = new_mode
        self._mode.enter(self)
        log.info("Mode → %s", self._mode.name)

    def toggle_scale_mode(self) -> None:
        """Toggle scale selection overlay on/off."""
        if self._mode is self._scale_mode:
            # Exiting scale mode — return to previous mode
            self._scale_mode.exit(self)
            self._mode = self._previous_mode or self._mixer_mode
            self._mode.enter(self)
            self._previous_mode = None
            log.info("Mode → %s (from scale)", self._mode.name)
        else:
            # Entering scale mode — save current mode
            self._previous_mode = self._mode
            self._mode.exit(self)
            self._mode = self._scale_mode
            self._mode.enter(self)

    def _setup_event_handlers(self) -> None:
        """Wire Push 2 events to Reaper actions."""
        self.event_bus.subscribe("button_pressed", self._on_button)
        self.event_bus.subscribe("button_released", self._on_button_released)
        self.event_bus.subscribe("encoder_rotated", self._on_encoder)
        self.event_bus.subscribe("pad_pressed", self._on_pad_pressed)
        self.event_bus.subscribe("pad_released", self._on_pad_released)
        self.event_bus.subscribe("pad_aftertouch", self._on_pad_aftertouch)
        self.event_bus.subscribe("touchstrip", self._on_touchstrip)
        self.event_bus.subscribe("state_changed", self._on_state_changed)

    # --- Global button handlers ---

    def _on_button(self, data: dict) -> None:
        button = data["button"]
        name = data["name"]

        # Shift button: track held state
        if button == c.BUTTON_SHIFT:
            self._shift_held = True
            return

        # Undo / Redo (Shift+Undo = Redo)
        if button == c.BUTTON_UNDO:
            if self._shift_held:
                self.osc_client.redo()
                log.info("→ Redo")
            else:
                self.osc_client.undo()
                log.info("→ Undo")
            return

        # Scale button: toggle scale overlay
        if button == c.BUTTON_SCALE:
            self.toggle_scale_mode()
            return

        # Octave buttons (always active)
        if button == c.BUTTON_OCTAVE_UP:
            self.scale_state.octave_up()
            if self.push2.pads:
                self.push2.pads.rebuild_grid()
            log.info("Octave up → base note %d", self.scale_state.base_note)
            return
        if button == c.BUTTON_OCTAVE_DOWN:
            self.scale_state.octave_down()
            if self.push2.pads:
                self.push2.pads.rebuild_grid()
            log.info("Octave down → base note %d", self.scale_state.base_note)
            return

        # Transport (global, not mode-dependent)
        if button == c.BUTTON_PLAY:
            self.osc_client.play()
            log.info("→ Play")
            return
        if button == c.BUTTON_STOP:
            self.osc_client.stop()
            log.info("→ Stop")
            return
        if button == c.BUTTON_RECORD:
            self.osc_client.record()
            log.info("→ Record")
            return
        if button == c.BUTTON_METRONOME:
            self.osc_client.click()
            log.info("→ Metronome toggle")
            return
        if button == c.BUTTON_REPEAT:
            self.osc_client.repeat()
            log.info("→ Repeat/Loop toggle")
            return

        # Bank navigation (global)
        if button == c.BUTTON_PAGE_LEFT:
            # Scale mode handles page_left/right itself
            if self._mode is self._scale_mode:
                self._mode.on_button(self, button, name)
                return
            self.osc_client.prev_track_bank()
            self.state.prev_bank()
            log.info("→ Bank left (tracks %d-%d)",
                     self.state.bank_offset + 1, self.state.bank_offset + 8)
            return
        if button == c.BUTTON_PAGE_RIGHT:
            if self._mode is self._scale_mode:
                self._mode.on_button(self, button, name)
                return
            self.osc_client.next_track_bank()
            self.state.next_bank()
            log.info("→ Bank right (tracks %d-%d)",
                     self.state.bank_offset + 1, self.state.bank_offset + 8)
            return

        # Track navigation (global)
        if button == c.BUTTON_LEFT:
            self.osc_client.prev_track()
            log.info("→ Prev track")
            return
        if button == c.BUTTON_RIGHT:
            self.osc_client.next_track()
            log.info("→ Next track")
            return

        # Master button (global)
        if button == c.BUTTON_MASTER:
            log.info("Master button pressed")
            return

        # Add Device: open FX browser for selected track
        if button == c.BUTTON_ADD_DEVICE:
            self.osc_client.trigger_action(40271)
            log.info("→ Add Device (FX browser)")
            return

        # Add Track: insert new track
        if button == c.BUTTON_ADD_TRACK:
            self.osc_client.trigger_action(40702)
            log.info("→ Add Track")
            return

        # Automation mode cycling for selected track
        if button == c.BUTTON_AUTOMATE:
            self._cycle_automation_mode()
            return

        # Mode switch buttons
        if button == c.BUTTON_MIX:
            self.switch_mode(self._mixer_mode)
            return
        if button == c.BUTTON_NOTE:
            if self._mode is self._drum_mode:
                self.switch_mode(self._mixer_mode)
            else:
                self.switch_mode(self._drum_mode)
            return
        if button == c.BUTTON_DEVICE:
            if self._mode is self._device_mode:
                self.switch_mode(self._mixer_mode)
            else:
                self.switch_mode(self._device_mode)
            return
        if button == c.BUTTON_SESSION:
            if self._mode is self._session_mode:
                self.switch_mode(self._mixer_mode)
            else:
                self.switch_mode(self._session_mode)
            return
        if button == c.BUTTON_BROWSE:
            if self._mode is self._browser_mode:
                self.switch_mode(self._mixer_mode)
            else:
                self.switch_mode(self._browser_mode)
            return

        # Delegate remaining buttons to current mode
        handled = self._mode.on_button(self, button, name)
        if not handled:
            # If scale mode didn't handle it, exit scale and re-dispatch
            if self._mode is self._scale_mode:
                self.toggle_scale_mode()
                self._mode.on_button(self, button, name)
            else:
                log.debug("Unhandled button: %s (%s)", name, button)

    # --- Automation ---

    _AUTOMODE_NAMES = {0: "Trim", 1: "Read", 2: "Touch", 3: "Write", 4: "Latch"}
    _AUTOMODE_COLORS = {0: "dark_gray", 1: "green", 2: "yellow", 3: "red", 4: "orange"}

    def _cycle_automation_mode(self) -> None:
        """Cycle automation mode for the selected track."""
        track_num = self.state.selected_track
        track = self.state.tracks.get(track_num)
        if track is None:
            return
        new_mode = (track.automode + 1) % 5
        self.osc_client.set_track_automode(track_num, new_mode)
        self.state.update_track(track_num, automode=new_mode)
        # Update button LED
        if self.push2.buttons:
            self.push2.buttons.set_color(
                c.BUTTON_AUTOMATE, self._AUTOMODE_COLORS.get(new_mode, "dark_gray")
            )
        log.info("→ Automation: %s (track %d)",
                 self._AUTOMODE_NAMES.get(new_mode, "?"), track_num)

    def _on_button_released(self, data: dict) -> None:
        button = data["button"]
        if button == c.BUTTON_SHIFT:
            self._shift_held = False

    # --- Delegate to current mode ---

    def _on_encoder(self, data: dict) -> None:
        self._mode.on_encoder(self, data["encoder"], data["increment"])

    def _on_pad_pressed(self, data: dict) -> None:
        row, col = data["pad_ij"]
        self._mode.on_pad_pressed(self, row, col, data["velocity"])

    def _on_pad_released(self, data: dict) -> None:
        row, col = data["pad_ij"]
        self._mode.on_pad_released(self, row, col)

    def _on_pad_aftertouch(self, data: dict) -> None:
        row, col = data["pad_ij"]
        self._mode.on_aftertouch(self, row, col, data["value"])

    def _on_touchstrip(self, data: dict) -> None:
        value = data["value"]
        # Touchstrip sends 0-16383 (14-bit); map to 0.0-1.0 for Reaper pitch bend
        normalized = value / 16383.0
        self.osc_client.pitch_bend(0, normalized)

    def _on_state_changed(self, data: dict) -> None:
        self._mode.on_state_changed(self, data or {})
        # Always update transport LEDs regardless of mode
        if data and data.get("type") == "transport":
            if self.push2.buttons:
                self.push2.buttons.set_transport_state(
                    self.state.playing, self.state.recording
                )

    # --- Main loop ---

    async def run(self) -> None:
        """Main event loop."""
        # Connect OSC
        self.osc_client.connect()
        self.osc_server.start()

        # Connect Push 2
        if not self.push2.connect():
            log.error("Could not connect to Push 2. Is it plugged in?")
            log.error("Check: udev rules installed? libusb available?")
            self.osc_server.stop()
            return

        self._running = True

        # Enter initial mode
        self._mode.enter(self)
        if self.push2.buttons:
            self.push2.buttons.set_transport_state(
                self.state.playing, self.state.recording
            )

        frame_interval = 1.0 / self._fps
        log.info("Starting display at %d fps", self._fps)
        log.info("OSC: sending to %s:%d, listening on :%d",
                 self.osc_client.ip, self.osc_client.port,
                 self.osc_server.port)
        log.info("Ready! Mode: %s", self._mode.name)

        try:
            while self._running:
                try:
                    frame = self._mode.render(self)
                    self.push2.display.send_frame(frame)
                except Exception:
                    log.exception("Display frame error")
                await asyncio.sleep(frame_interval)
        except asyncio.CancelledError:
            log.info("Display loop cancelled")
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Clean shutdown."""
        self._running = False
        log.info("Shutting down...")
        self.osc_server.stop()
        self.push2.disconnect()
        log.info("Shutdown complete")


def main() -> None:
    setup_logging()
    log.info("=== Push 2 Reaper Controller ===")

    config = load_config()
    daemon = Push2ReaperDaemon(config)

    loop = asyncio.new_event_loop()

    def signal_handler():
        log.info("Signal received, stopping...")
        daemon._running = False

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        loop.run_until_complete(daemon.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
