"""Device/FX parameter display screen.

Shows the current FX plugin name and 8 parameter knobs with labels and values.
"""

import logging
import math
from PIL import Image, ImageDraw, ImageFont

from reaper.state import ReaperState, FXInfo

log = logging.getLogger("push2reaper.ui.device_screen")

WIDTH = 960
HEIGHT = 160
STRIP_W = WIDTH // 8

BG = (0, 0, 0)
TEXT = (220, 220, 220)
TEXT_DIM = (120, 120, 120)
ACCENT = (255, 120, 0)
KNOB_COLOR = (100, 180, 255)
KNOB_BG = (40, 40, 40)
KNOB_TRACK = (60, 60, 60)
SEPARATOR = (50, 50, 50)


class DeviceScreen:
    """Renders FX parameter controls."""

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

    def render(self, state: ReaperState, track_num: int,
               fx_idx: int, param_bank: int) -> Image.Image:
        """Render device parameter screen.

        Args:
            state: Reaper state
            track_num: Track number (1-indexed)
            fx_idx: FX index (0-based)
            param_bank: Parameter bank (0-based, 8 params per bank)
        """
        img = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(img)

        track = state.tracks.get(track_num)
        track_name = track.name if track else f"Track {track_num}"

        # Get FX info
        fx_list = state.fx.get(track_num, [])
        fx = fx_list[fx_idx] if fx_idx < len(fx_list) else None
        fx_name = fx.name if fx else f"FX {fx_idx + 1}"

        # Header
        draw.rectangle([0, 0, WIDTH, 24], fill=(30, 30, 30))
        draw.text(
            (10, 12), f"DEVICE",
            fill=ACCENT, font=self._font, anchor="lm",
        )
        draw.text(
            (120, 12), f"{track_name} > {fx_name}",
            fill=TEXT, font=self._font_small, anchor="lm",
        )

        fx_count = len(fx_list)
        draw.text(
            (WIDTH - 10, 12),
            f"FX {fx_idx + 1}/{fx_count}" if fx_count > 0 else "No FX",
            fill=TEXT_DIM, font=self._font_small, anchor="rm",
        )

        # Draw 8 parameter knobs
        params = fx.params if fx else []
        param_start = param_bank * 8

        for i in range(8):
            x = i * STRIP_W
            param_idx = param_start + i
            if param_idx < len(params):
                param = params[param_idx]
                self._draw_param_knob(draw, x, param)
            else:
                self._draw_empty_knob(draw, x)
            # Separator
            draw.line([x + STRIP_W - 1, 24, x + STRIP_W - 1, HEIGHT],
                      fill=SEPARATOR)

        # Bank indicator at bottom
        total_params = len(params) if params else 0
        total_banks = max(1, (total_params + 7) // 8)
        draw.text(
            (WIDTH // 2, HEIGHT - 6),
            f"Bank {param_bank + 1}/{total_banks}",
            fill=TEXT_DIM, font=self._font_tiny, anchor="mm",
        )

        return img

    def _draw_param_knob(self, draw: ImageDraw.ImageDraw, x: int,
                         param: dict) -> None:
        """Draw a parameter knob with name and value."""
        cx = x + STRIP_W // 2

        # Param name
        name = param.get("name", "?")[:12]
        draw.text((cx, 36), name, fill=TEXT, font=self._font_small, anchor="mm")

        # Knob (arc indicator)
        knob_cx = cx
        knob_cy = 78
        knob_r = 22

        # Background arc
        draw.arc(
            [knob_cx - knob_r, knob_cy - knob_r,
             knob_cx + knob_r, knob_cy + knob_r],
            start=135, end=405, fill=KNOB_TRACK, width=4,
        )

        # Value arc
        value = param.get("value", 0.0)
        if value > 0.0:
            end_angle = 135 + int(value * 270)
            draw.arc(
                [knob_cx - knob_r, knob_cy - knob_r,
                 knob_cx + knob_r, knob_cy + knob_r],
                start=135, end=end_angle, fill=KNOB_COLOR, width=4,
            )

        # Value indicator dot
        angle_rad = math.radians(135 + value * 270)
        dot_x = knob_cx + int((knob_r - 2) * math.cos(angle_rad))
        dot_y = knob_cy + int((knob_r - 2) * math.sin(angle_rad))
        draw.ellipse([dot_x - 3, dot_y - 3, dot_x + 3, dot_y + 3],
                     fill=KNOB_COLOR)

        # Value text
        draw.text(
            (cx, knob_cy + knob_r + 10),
            f"{value:.0%}",
            fill=TEXT_DIM, font=self._font_tiny, anchor="mm",
        )

    def _draw_empty_knob(self, draw: ImageDraw.ImageDraw, x: int) -> None:
        cx = x + STRIP_W // 2
        draw.text((cx, 78), "—", fill=TEXT_DIM, font=self._font_small, anchor="mm")
