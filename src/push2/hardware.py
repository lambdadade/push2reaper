"""Push 2 hardware connection and event routing.

Wraps push2-python, registers MIDI event handlers, and publishes
events to the application event bus.
"""

import logging
import push2_python
import push2_python.constants as c

from core.event_bus import EventBus
from push2.display import Push2Display
from push2.pads import PadManager
from push2.scales import ScaleState
from push2.buttons import ButtonManager, BUTTON_NAME_LOOKUP
from push2.encoders import EncoderManager
from push2.colors import setup_custom_palette

log = logging.getLogger("push2reaper.push2.hardware")


class Push2Hardware:
    """Manages Push 2 hardware connection and input/output."""

    def __init__(self, event_bus: EventBus, config: dict = None,
                 scale_state: ScaleState | None = None):
        self.event_bus = event_bus
        self.config = config or {}
        self._scale_state = scale_state
        self.push: push2_python.Push2 | None = None
        self.display: Push2Display | None = None
        self.pads: PadManager | None = None
        self.buttons: ButtonManager | None = None
        self.encoders: EncoderManager = EncoderManager()
        self._connected = False
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register push2-python decorator-based event handlers.

        These must be registered before Push2() is instantiated (they
        go into a global registry that Push2.__init__ picks up).
        """

        @push2_python.on_midi_connected()
        def on_midi_connected(push):
            log.info("Push 2 MIDI connected")
            self._connected = True
            self.event_bus.publish("push2_midi_connected")

        @push2_python.on_midi_disconnected()
        def on_midi_disconnected(push):
            log.warning("Push 2 MIDI disconnected")
            self._connected = False
            self.event_bus.publish("push2_midi_disconnected")

        @push2_python.on_display_connected()
        def on_display_connected(push):
            log.info("Push 2 display connected")
            self.event_bus.publish("push2_display_connected")

        @push2_python.on_display_disconnected()
        def on_display_disconnected(push):
            log.warning("Push 2 display disconnected")
            self.event_bus.publish("push2_display_disconnected")

        # --- Pad events ---
        @push2_python.on_pad_pressed()
        def on_pad_pressed(push, pad_n, pad_ij, velocity):
            log.debug("Pad pressed: ij=%s vel=%d", pad_ij, velocity)
            self.event_bus.publish("pad_pressed", {
                "pad_n": pad_n,
                "pad_ij": pad_ij,
                "velocity": velocity,
            })

        @push2_python.on_pad_released()
        def on_pad_released(push, pad_n, pad_ij, velocity):
            self.event_bus.publish("pad_released", {
                "pad_n": pad_n,
                "pad_ij": pad_ij,
                "velocity": velocity,
            })

        @push2_python.on_pad_aftertouch()
        def on_pad_aftertouch(push, pad_n, pad_ij, value):
            self.event_bus.publish("pad_aftertouch", {
                "pad_n": pad_n,
                "pad_ij": pad_ij,
                "value": value,
            })

        # --- Button events ---
        @push2_python.on_button_pressed()
        def on_button_pressed(push, button_name):
            friendly = BUTTON_NAME_LOOKUP.get(button_name, button_name)
            log.debug("Button pressed: %s (%s)", friendly, button_name)
            self.event_bus.publish("button_pressed", {
                "button": button_name,
                "name": friendly,
            })

        @push2_python.on_button_released()
        def on_button_released(push, button_name):
            friendly = BUTTON_NAME_LOOKUP.get(button_name, button_name)
            self.event_bus.publish("button_released", {
                "button": button_name,
                "name": friendly,
            })

        # --- Encoder events ---
        @push2_python.on_encoder_rotated()
        def on_encoder_rotated(push, encoder_name, increment):
            log.debug("Encoder: %s %+d", encoder_name, increment)
            self.event_bus.publish("encoder_rotated", {
                "encoder": encoder_name,
                "increment": increment,
            })

        @push2_python.on_encoder_touched()
        def on_encoder_touched(push, encoder_name):
            self.encoders.on_touch(encoder_name)
            self.event_bus.publish("encoder_touched", {
                "encoder": encoder_name,
            })

        @push2_python.on_encoder_released()
        def on_encoder_released(push, encoder_name):
            self.encoders.on_release(encoder_name)
            self.event_bus.publish("encoder_released", {
                "encoder": encoder_name,
            })

        # --- Touchstrip ---
        @push2_python.on_touchstrip()
        def on_touchstrip(push, value):
            self.event_bus.publish("touchstrip", {"value": value})

        # --- Sustain pedal ---
        @push2_python.on_sustain_pedal()
        def on_sustain(push, sustain_on):
            self.event_bus.publish("sustain_pedal", {"on": sustain_on})

    def connect(self) -> bool:
        """Initialize Push 2 hardware connection.

        Returns True if MIDI connection succeeded.
        """
        try:
            log.info("Connecting to Push 2...")
            use_user_port = self.config.get("push2", {}).get("use_user_midi_port", False)
            self.push = push2_python.Push2(use_user_midi_port=use_user_port)

            # Initialize sub-managers
            self.display = Push2Display(self.push)
            self.pads = PadManager(self.push, scale_state=self._scale_state)
            self.buttons = ButtonManager(self.push)

            # Set up custom color palette
            setup_custom_palette(self.push)

            # Ensure MIDI OUT is configured before sending LED colors.
            # Push2.__init__ only configures MIDI IN; MIDI OUT is lazy but
            # rate-limited, so the first send_midi_to_push can silently fail.
            self.push.configure_midi_out()

            # Set initial hardware state
            self.buttons.init_defaults()
            self.pads.init_default_layout()

            self._connected = True
            log.info("Push 2 connected successfully")
            return True

        except Exception:
            log.exception("Failed to connect to Push 2")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Clean up Push 2 connection."""
        if self.push is not None:
            # Each cleanup step is independent — don't let one failure block others
            for name, action in [
                ("display", lambda: self.display and self.display.send_black()),
                ("buttons", lambda: self.buttons and self.buttons.clear_all()),
                ("pads", lambda: self.pads and self.pads.clear()),
            ]:
                try:
                    action()
                except Exception:
                    log.debug("Cleanup failed for %s (expected on USB disconnect)", name)
            self.push = None
            self._connected = False
            log.info("Push 2 disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected
