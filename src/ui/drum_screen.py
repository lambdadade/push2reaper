"""Drum mode display screen.

Shows the selected drum pad, bank position, and step sequencer info.
"""

import logging
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("push2reaper.ui.drum_screen")

WIDTH = 960
HEIGHT = 160

BG = (0, 0, 0)
TEXT = (220, 220, 220)
TEXT_DIM = (120, 120, 120)
ACCENT = (255, 120, 0)
PAD_ACTIVE = (100, 200, 100)
PAD_SELECTED = (255, 200, 50)
SEPARATOR = (50, 50, 50)

# GM drum note names (notes 36-51)
GM_DRUM_NAMES = [
    "Kick", "Side Stick", "Snare", "Clap",
    "Snare Edge", "Low Tom", "Hi-Hat Cl", "Low Tom 2",
    "Hi-Hat Ped", "Mid Tom", "Hi-Hat Op", "Mid Tom 2",
    "High Tom", "Crash", "High Tom 2", "Ride",
]


class DrumScreen:
    """Renders the drum mode display."""

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

    def render(self, selected_pad: int, bank_offset: int,
               step_grid: list[bool] | None = None) -> Image.Image:
        """Render drum mode display.

        Args:
            selected_pad: Currently selected drum pad index (0-15 within bank)
            bank_offset: Base MIDI note for current bank (e.g. 36)
            step_grid: Optional 16-step pattern for selected pad
        """
        img = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(img)

        note = bank_offset + selected_pad
        pad_name = self._note_name(note)

        # Header
        draw.rectangle([0, 0, WIDTH, 24], fill=(30, 30, 30))
        draw.text(
            (10, 12), f"DRUM MODE",
            fill=ACCENT, font=self._font, anchor="lm",
        )
        draw.text(
            (200, 12), f"Pad: {pad_name} (Note {note})",
            fill=TEXT, font=self._font, anchor="lm",
        )
        draw.text(
            (WIDTH - 10, 12), f"Bank: {bank_offset}-{bank_offset + 15}",
            fill=TEXT_DIM, font=self._font_small, anchor="rm",
        )

        # Draw 4x4 pad grid overview
        grid_x = 30
        grid_y = 35
        pad_size = 25
        pad_gap = 3

        for row in range(4):
            for col in range(4):
                pad_idx = row * 4 + col
                px = grid_x + col * (pad_size + pad_gap)
                py = grid_y + row * (pad_size + pad_gap)

                if pad_idx == selected_pad:
                    color = PAD_SELECTED
                else:
                    color = (60, 60, 60)

                draw.rectangle([px, py, px + pad_size, py + pad_size], fill=color)

                n = bank_offset + pad_idx
                draw.text(
                    (px + pad_size // 2, py + pad_size // 2),
                    str(n), fill=(0, 0, 0) if pad_idx == selected_pad else TEXT_DIM,
                    font=self._font_tiny, anchor="mm",
                )

        # Pad name list (right side)
        list_x = 180
        for i in range(16):
            n = bank_offset + i
            name = self._note_name(n)
            y = 30 + i * 8
            if y > HEIGHT - 10:
                break
            color = PAD_SELECTED if i == selected_pad else TEXT_DIM
            draw.text((list_x, y), f"{n}: {name}", fill=color,
                      font=self._font_tiny, anchor="lm")

        # Step grid (if available) — 16 steps across the right portion
        if step_grid is not None:
            step_y = 80
            step_x_start = 500
            step_size = 26
            step_gap = 2

            draw.text(
                (step_x_start, step_y - 12), "Steps:",
                fill=TEXT_DIM, font=self._font_small, anchor="lm",
            )

            for i in range(16):
                sx = step_x_start + (i % 8) * (step_size + step_gap)
                sy = step_y + (i // 8) * (step_size + step_gap)

                if step_grid[i]:
                    color = PAD_ACTIVE
                else:
                    color = (40, 40, 40)

                draw.rectangle([sx, sy, sx + step_size, sy + step_size],
                               fill=color, outline=(80, 80, 80))

        return img

    @staticmethod
    def _note_name(note: int) -> str:
        """Get a human-readable name for a MIDI note in drum context."""
        if 36 <= note <= 51:
            return GM_DRUM_NAMES[note - 36]
        note_names = ["C", "C#", "D", "D#", "E", "F",
                       "F#", "G", "G#", "A", "A#", "B"]
        octave = (note // 12) - 1
        return f"{note_names[note % 12]}{octave}"
