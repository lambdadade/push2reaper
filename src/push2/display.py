"""Push 2 display rendering engine.

Renders PIL images and sends them as BGR565 numpy frames
to the Push 2's 960x160 pixel display.
"""

import logging
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from push2_python.constants import FRAME_FORMAT_BGR565

log = logging.getLogger("push2reaper.push2.display")

WIDTH = 960
HEIGHT = 160


def pil_to_bgr565(img: Image.Image) -> np.ndarray:
    """Convert a PIL RGB image to BGR565 uint16 numpy array (960, 160)."""
    rgb = np.array(img.convert("RGB"))  # (160, 960, 3) uint8

    r = (rgb[:, :, 0] >> 3).astype(np.uint16)
    g = (rgb[:, :, 1] >> 2).astype(np.uint16)
    b = (rgb[:, :, 2] >> 3).astype(np.uint16)

    # BGR565: BBBBB_GGGGGG_RRRRR
    bgr565 = (b << 11) | (g << 5) | r  # (160, 960)

    # push2-python expects shape (960, 160) — transposed
    return bgr565.T


class Push2Display:
    """Manages rendering and sending frames to Push 2 display."""

    def __init__(self, push):
        self._push = push
        self._font = None
        self._font_small = None
        self._load_fonts()

    def _load_fonts(self) -> None:
        """Load fonts for display rendering."""
        try:
            self._font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
            self._font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        except OSError:
            log.warning("DejaVu fonts not found, using default bitmap font")
            self._font = ImageFont.load_default()
            self._font_small = self._font

    def send_frame(self, img: Image.Image) -> None:
        """Convert PIL image and send to Push 2 display."""
        frame = pil_to_bgr565(img)
        self._push.display.display_frame(frame, input_format=FRAME_FORMAT_BGR565)

    def send_black(self) -> None:
        """Send a black frame (clears display)."""
        frame = np.zeros((WIDTH, HEIGHT), dtype=np.uint16)
        self._push.display.display_frame(frame, input_format=FRAME_FORMAT_BGR565)

    def render_test_pattern(self) -> Image.Image:
        """Render a test pattern with colored bars and text."""
        img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 8 colored column strips (120px each)
        colors = [
            (255, 60, 60),    # red
            (255, 140, 30),   # orange
            (255, 220, 50),   # yellow
            (50, 200, 80),    # green
            (50, 200, 200),   # turquoise
            (60, 100, 255),   # blue
            (160, 80, 220),   # purple
            (240, 100, 180),  # pink
        ]

        strip_w = WIDTH // 8
        for i, color in enumerate(colors):
            x = i * strip_w
            # Draw colored header bar
            draw.rectangle([x, 0, x + strip_w - 2, 40], fill=color)
            # Track number
            draw.text(
                (x + strip_w // 2, 12),
                f"Track {i + 1}",
                fill=(0, 0, 0),
                font=self._font_small,
                anchor="mt",
            )
            # Fake fader
            fader_h = 60 + i * 8
            draw.rectangle(
                [x + 50, 140 - fader_h, x + 70, 140],
                fill=color,
                outline=(80, 80, 80),
            )

        # Title text
        draw.text(
            (WIDTH // 2, 80),
            "Push 2 Reaper",
            fill=(255, 255, 255),
            font=self._font,
            anchor="mm",
        )
        draw.text(
            (WIDTH // 2, 100),
            "Controller Ready",
            fill=(180, 180, 180),
            font=self._font_small,
            anchor="mm",
        )

        return img

    @property
    def font(self) -> ImageFont.FreeTypeFont:
        return self._font

    @property
    def font_small(self) -> ImageFont.FreeTypeFont:
        return self._font_small
