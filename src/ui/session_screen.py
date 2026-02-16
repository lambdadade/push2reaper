"""Session/clip launcher display screen.

Shows clip grid with real-time state from Playtime.
"""

import logging
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("push2reaper.ui.session_screen")

WIDTH = 960
HEIGHT = 160
STRIP_W = WIDTH // 8

BG = (0, 0, 0)
TEXT = (220, 220, 220)
TEXT_DIM = (120, 120, 120)
ACCENT = (255, 120, 0)
SEPARATOR = (50, 50, 50)

# Clip state colors (match playtime.client constants)
STATE_COLORS = {
    0: (30, 30, 30),       # empty
    1: (70, 70, 80),       # stopped (has content)
    2: (50, 200, 80),      # playing
    3: (255, 60, 60),      # recording
    4: (255, 220, 50),     # queued
}


class SessionScreen:
    """Renders the session/clip grid view."""

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

    def render(self, track_names: list[str], scene_offset: int,
               clip_states: list[list[int]] | None = None,
               connected: bool = False,
               num_columns: int = 0,
               num_rows: int = 0) -> Image.Image:
        img = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(img)

        # Header with track names
        header_color = (30, 40, 30) if connected else (40, 30, 30)
        draw.rectangle([0, 0, WIDTH, 20], fill=header_color)
        for i in range(8):
            x = i * STRIP_W
            name = track_names[i][:10] if i < len(track_names) else ""
            # Dim tracks beyond Playtime's column count
            color = TEXT if (i < num_columns or not connected) else TEXT_DIM
            draw.text(
                (x + STRIP_W // 2, 10), name,
                fill=color, font=self._font_small, anchor="mm",
            )

        # Clip grid
        grid_top = 22
        row_h = (HEIGHT - grid_top - 14) // 8
        cell_w = STRIP_W - 4

        for row in range(8):
            for col in range(8):
                x = col * STRIP_W + 2
                y = grid_top + row * row_h

                state = 0
                if clip_states and row < len(clip_states) and col < len(clip_states[row]):
                    state = clip_states[row][col]

                fill = STATE_COLORS.get(state, STATE_COLORS[0])

                # Draw cell with outline
                outline = (80, 80, 80) if state > 0 else (40, 40, 40)
                draw.rectangle([x, y, x + cell_w, y + row_h - 2],
                               fill=fill, outline=outline)

                # Playing indicator: draw a small triangle
                if state == 2:  # playing
                    cx = x + cell_w // 2
                    cy = y + row_h // 2 - 1
                    draw.polygon([(cx - 3, cy - 3), (cx - 3, cy + 3), (cx + 3, cy)],
                                 fill=(255, 255, 255))
                # Recording indicator: small circle
                elif state == 3:
                    cx = x + cell_w // 2
                    cy = y + row_h // 2 - 1
                    draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3],
                                 fill=(255, 255, 255))

            # Scene number on right edge
            draw.text(
                (WIDTH - 4, grid_top + row * row_h + row_h // 2),
                str(scene_offset + row + 1),
                fill=TEXT_DIM, font=self._font_tiny, anchor="rm",
            )

        # Column separators
        for i in range(8):
            x = i * STRIP_W
            draw.line([x, 20, x, HEIGHT], fill=SEPARATOR)

        # Footer
        if connected:
            status = f"SESSION  |  Scenes {scene_offset + 1}-{scene_offset + 8}  |  Playtime ({num_columns}x{num_rows})"
        else:
            status = f"SESSION  |  Scenes {scene_offset + 1}-{scene_offset + 8}  |  No Playtime"
        draw.text(
            (WIDTH // 2, HEIGHT - 4), status,
            fill=TEXT_DIM, font=self._font_tiny, anchor="mm",
        )

        return img
