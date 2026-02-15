"""Base class for Push 2 operating modes.

Each mode controls how the Push 2 pads, encoders, buttons, and display
behave. The daemon delegates input events and display rendering to
the currently active mode.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from main import Push2ReaperDaemon


class Mode:
    """Base class for all Push 2 operating modes."""

    name: str = "base"

    def enter(self, daemon: Push2ReaperDaemon) -> None:
        """Called when this mode becomes active."""

    def exit(self, daemon: Push2ReaperDaemon) -> None:
        """Called when leaving this mode."""

    def on_button(self, daemon: Push2ReaperDaemon, button: str, name: str) -> bool:
        """Handle a button press. Return True if handled."""
        return False

    def on_encoder(self, daemon: Push2ReaperDaemon, encoder: str, increment: int) -> None:
        """Handle encoder rotation."""

    def on_pad_pressed(self, daemon: Push2ReaperDaemon, row: int, col: int, velocity: int) -> None:
        """Handle pad press."""

    def on_pad_released(self, daemon: Push2ReaperDaemon, row: int, col: int) -> None:
        """Handle pad release."""

    def on_aftertouch(self, daemon: Push2ReaperDaemon, row: int, col: int, value: int) -> None:
        """Handle pad aftertouch."""

    def on_state_changed(self, daemon: Push2ReaperDaemon, data: dict) -> None:
        """Handle Reaper state change (for updating LEDs etc)."""

    def render(self, daemon: Push2ReaperDaemon) -> Image.Image:
        """Render the display for this mode. Must return 960x160 RGB image."""
        return Image.new("RGB", (960, 160), (0, 0, 0))
