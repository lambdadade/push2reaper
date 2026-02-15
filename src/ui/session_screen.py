"""Session/clip launcher display screen.

Shows an 8x8 grid representing tracks (columns) and clip slots (rows).
Designed to work with Helgoboss Playtime via ReaLearn targets.
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

# Clip state colors
CLIP_EMPTY = (30, 30, 30)
CLIP_STOPPED = (60, 60, 60)
CLIP_PLAYING = (50, 200, 80)
CLIP_RECORDING = (255, 60, 60)
CLIP_QUEUED = (255, 220, 50)


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
               clip_states: list[list[int]] | None = None) -> Image.Image:
        """Render session view.

        Args:
            track_names: List of 8 track names for current bank
            scene_offset: First visible scene/row index
            clip_states: 8x8 grid of clip states (0=empty, 1=stopped,
                        2=playing, 3=recording, 4=queued)
        """
        img = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(img)

        # Header with track names
        draw.rectangle([0, 0, WIDTH, 20], fill=(30, 30, 30))
        for i in range(8):
            x = i * STRIP_W
            name = track_names[i][:10] if i < len(track_names) else ""
            draw.text(
                (x + STRIP_W // 2, 10), name,
                fill=TEXT, font=self._font_small, anchor="mm",
            )

        # Clip grid (8 cols x 8 rows, fitting in remaining space)
        grid_top = 22
        row_h = (HEIGHT - grid_top - 14) // 8  # leave room for footer
        cell_w = STRIP_W - 4

        state_colors = {
            0: CLIP_EMPTY, 1: CLIP_STOPPED, 2: CLIP_PLAYING,
            3: CLIP_RECORDING, 4: CLIP_QUEUED,
        }

        for row in range(8):
            for col in range(8):
                x = col * STRIP_W + 2
                y = grid_top + row * row_h

                state = 0
                if clip_states and row < len(clip_states) and col < len(clip_states[row]):
                    state = clip_states[row][col]

                color = state_colors.get(state, CLIP_EMPTY)
                draw.rectangle([x, y, x + cell_w, y + row_h - 2],
                               fill=color, outline=(50, 50, 50))

            # Scene number on the right edge
            draw.text(
                (WIDTH - 4, grid_top + row * row_h + row_h // 2),
                str(scene_offset + row + 1),
                fill=TEXT_DIM, font=self._font_tiny, anchor="rm",
            )

        # Separators
        for i in range(8):
            x = i * STRIP_W
            draw.line([x, 20, x, HEIGHT], fill=SEPARATOR)

        # Footer
        draw.text(
            (WIDTH // 2, HEIGHT - 4),
            f"SESSION  |  Scenes {scene_offset + 1}-{scene_offset + 8}  |  Playtime",
            fill=TEXT_DIM, font=self._font_tiny, anchor="mm",
        )

        return img
