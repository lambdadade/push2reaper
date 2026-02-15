"""Push 2 button state and LED management."""

import logging
import push2_python.constants as c

log = logging.getLogger("push2reaper.push2.buttons")

# Transport buttons
TRANSPORT_BUTTONS = {
    "play": c.BUTTON_PLAY,
    "stop": c.BUTTON_STOP,
    "record": c.BUTTON_RECORD,
}

# Navigation buttons
NAV_BUTTONS = {
    "up": c.BUTTON_UP,
    "down": c.BUTTON_DOWN,
    "left": c.BUTTON_LEFT,
    "right": c.BUTTON_RIGHT,
    "page_left": c.BUTTON_PAGE_LEFT,
    "page_right": c.BUTTON_PAGE_RIGHT,
}

# Track function buttons
TRACK_BUTTONS = {
    "mute": c.BUTTON_MUTE,
    "solo": c.BUTTON_SOLO,
    "master": c.BUTTON_MASTER,
}

# Mode selection buttons
MODE_BUTTONS = {
    "mix": c.BUTTON_MIX,
    "device": c.BUTTON_DEVICE,
    "browse": c.BUTTON_BROWSE,
    "clip": c.BUTTON_CLIP,
    "session": c.BUTTON_SESSION,
    "note": c.BUTTON_NOTE,
}

# Upper/lower row buttons (above/below display)
UPPER_ROW = [
    c.BUTTON_UPPER_ROW_1, c.BUTTON_UPPER_ROW_2, c.BUTTON_UPPER_ROW_3,
    c.BUTTON_UPPER_ROW_4, c.BUTTON_UPPER_ROW_5, c.BUTTON_UPPER_ROW_6,
    c.BUTTON_UPPER_ROW_7, c.BUTTON_UPPER_ROW_8,
]

LOWER_ROW = [
    c.BUTTON_LOWER_ROW_1, c.BUTTON_LOWER_ROW_2, c.BUTTON_LOWER_ROW_3,
    c.BUTTON_LOWER_ROW_4, c.BUTTON_LOWER_ROW_5, c.BUTTON_LOWER_ROW_6,
    c.BUTTON_LOWER_ROW_7, c.BUTTON_LOWER_ROW_8,
]

# All known button names for reverse lookup
ALL_BUTTONS = {}
ALL_BUTTONS.update(TRANSPORT_BUTTONS)
ALL_BUTTONS.update(NAV_BUTTONS)
ALL_BUTTONS.update(TRACK_BUTTONS)
ALL_BUTTONS.update(MODE_BUTTONS)
for i, btn in enumerate(UPPER_ROW):
    ALL_BUTTONS[f"upper_row_{i+1}"] = btn
for i, btn in enumerate(LOWER_ROW):
    ALL_BUTTONS[f"lower_row_{i+1}"] = btn

# Reverse mapping: constant name → friendly name
BUTTON_NAME_LOOKUP = {v: k for k, v in ALL_BUTTONS.items()}


class ButtonManager:
    """Manages Push 2 button LED states."""

    def __init__(self, push):
        self._push = push
        self._states: dict[str, str] = {}  # button_const -> color

    def set_color(self, button_const: str, color: str) -> None:
        if self._states.get(button_const) == color:
            return  # skip redundant MIDI
        self._push.buttons.set_button_color(button_const, color)
        self._states[button_const] = color

    def set_transport_state(self, playing: bool, recording: bool) -> None:
        self.set_color(c.BUTTON_PLAY, "green" if playing else "dark_gray")
        self.set_color(c.BUTTON_RECORD, "red" if recording else "dark_gray")

    def clear_all(self) -> None:
        self._push.buttons.set_all_buttons_color("black")
        self._states.clear()

    def init_defaults(self) -> None:
        """Set initial button colors after connection."""
        # RGB buttons (Color: True) — use RGB color names
        self.set_color(c.BUTTON_PLAY, "dark_gray")
        self.set_color(c.BUTTON_STOP, "dark_gray")
        self.set_color(c.BUTTON_RECORD, "dark_gray")
        self.set_color(c.BUTTON_AUTOMATE, "dark_gray")
        self.set_color(c.BUTTON_MUTE, "dark_gray")
        self.set_color(c.BUTTON_SOLO, "dark_gray")
        for btn in UPPER_ROW + LOWER_ROW:
            self.set_color(btn, "dark_gray")
        # Subdivision row
        for btn in [c.BUTTON_1_32T, c.BUTTON_1_32, c.BUTTON_1_16T,
                    c.BUTTON_1_16, c.BUTTON_1_8T, c.BUTTON_1_8,
                    c.BUTTON_1_4T, c.BUTTON_1_4]:
            self.set_color(btn, "dark_gray")

        # BW-only buttons (Color: False) — use BW color names
        for btn in [c.BUTTON_TAP_TEMPO, c.BUTTON_METRONOME,
                    c.BUTTON_DELETE, c.BUTTON_UNDO,
                    c.BUTTON_CONVERT, c.BUTTON_DOUBLE_LOOP,
                    c.BUTTON_QUANTIZE, c.BUTTON_DUPLICATE,
                    c.BUTTON_NEW, c.BUTTON_FIXED_LENGTH,
                    c.BUTTON_SETUP, c.BUTTON_USER,
                    c.BUTTON_ADD_DEVICE, c.BUTTON_ADD_TRACK,
                    c.BUTTON_DEVICE, c.BUTTON_MIX,
                    c.BUTTON_BROWSE, c.BUTTON_CLIP,
                    c.BUTTON_MASTER,
                    c.BUTTON_UP, c.BUTTON_DOWN,
                    c.BUTTON_LEFT, c.BUTTON_RIGHT,
                    c.BUTTON_REPEAT, c.BUTTON_ACCENT,
                    c.BUTTON_SCALE, c.BUTTON_LAYOUT,
                    c.BUTTON_NOTE, c.BUTTON_SESSION,
                    c.BUTTON_OCTAVE_UP, c.BUTTON_OCTAVE_DOWN,
                    c.BUTTON_PAGE_LEFT, c.BUTTON_PAGE_RIGHT,
                    c.BUTTON_SHIFT, c.BUTTON_SELECT]:
            self.set_color(btn, "dark_gray")

        log.info("Button defaults initialized")
