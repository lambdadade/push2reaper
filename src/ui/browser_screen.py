"""Browser mode display screen.

Shows a simple browser navigation interface for FX/presets.
"""

import logging
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("push2reaper.ui.browser_screen")

WIDTH = 960
HEIGHT = 160

BG = (0, 0, 0)
TEXT = (220, 220, 220)
TEXT_DIM = (120, 120, 120)
ACCENT = (255, 120, 0)
HIGHLIGHT = (60, 100, 200)


class BrowserScreen:
    """Renders the FX/preset browser display."""

    def __init__(self):
        self._font: ImageFont.FreeTypeFont | None = None
        self._font_small: ImageFont.FreeTypeFont | None = None
        self._font_tiny: ImageFont.FreeTypeFont | None = None
        self._load_fonts()

    def _load_fonts(self) -> None:
        try:
            self._font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14
            )
            self._font_small = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11
            )
            self._font_tiny = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9
            )
        except OSError:
            self._font = ImageFont.load_default()
            self._font_small = self._font
            self._font_tiny = self._font

    def render(self, track_name: str, instructions: list[str] | None = None) -> Image.Image:
        """Render browser mode display.

        Args:
            track_name: Current track name
            instructions: List of help text lines
        """
        img = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([0, 0, WIDTH, 24], fill=(30, 30, 30))
        draw.text(
            (10, 12), "BROWSE",
            fill=ACCENT, font=self._font, anchor="lm",
        )
        draw.text(
            (150, 12), f"Track: {track_name}",
            fill=TEXT, font=self._font_small, anchor="lm",
        )

        # Instructions
        if instructions is None:
            instructions = [
                "Encoder 1: Navigate browser items (prev/next)",
                "Upper Row 1: Open FX browser for track",
                "Upper Row 2: Open FX chain window",
                "Upper Row 3: Add instrument to track",
                "Lower Row: Select track",
                "",
                "Browser navigation requires Reaper's FX window.",
                "Use the encoder to scroll through presets/FX.",
            ]

        y = 36
        for line in instructions:
            if y > HEIGHT - 10:
                break
            draw.text((30, y), line, fill=TEXT_DIM, font=self._font_small,
                      anchor="lm")
            y += 16

        return img
