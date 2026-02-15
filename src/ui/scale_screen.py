"""Scale selection display screen for Push 2."""

import logging
from PIL import Image, ImageDraw, ImageFont

from push2.scales import (ScaleState, SCALE_LIST, LAYOUT_LIST,
                           ROOT_NAMES, SCALE_PAGES, TOTAL_PAGES)

log = logging.getLogger("push2reaper.ui.scale_screen")

WIDTH = 960
HEIGHT = 160
COL_W = WIDTH // 8  # 120px per column

BG = (0, 0, 0)
TEXT = (220, 220, 220)
TEXT_DIM = (100, 100, 100)
HEADER_BG = (30, 30, 50)
ROOT_SELECTED_BG = (30, 50, 140)
SCALE_SELECTED_BG = (20, 100, 100)
LAYOUT_SELECTED_BG = (100, 60, 20)


class ScaleScreen:
    """Renders the scale selection UI on Push 2 display."""

    def __init__(self):
        self._font: ImageFont.FreeTypeFont | None = None
        self._font_small: ImageFont.FreeTypeFont | None = None
        self._font_tiny: ImageFont.FreeTypeFont | None = None
        self._load_fonts()

    def _load_fonts(self) -> None:
        try:
            self._font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16
            )
            self._font_small = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13
            )
            self._font_tiny = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10
            )
        except OSError:
            self._font = ImageFont.load_default()
            self._font_small = self._font
            self._font_tiny = self._font

    def render(self, scale_state: ScaleState) -> Image.Image:
        img = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(img)

        self._draw_header(draw, scale_state)
        self._draw_root_row(draw, scale_state)

        if scale_state.is_settings_page:
            self._draw_settings_row(draw, scale_state)
        else:
            self._draw_scale_row(draw, scale_state)

        return img

    def _draw_header(self, draw: ImageDraw.Draw, s: ScaleState) -> None:
        """Top banner with current selection."""
        draw.rectangle([0, 0, WIDTH, 30], fill=HEADER_BG)
        in_key_str = "In Key" if s.in_key else "Chromatic"
        text = (f"Scale: {s.scale_name}    Root: {s.root_name}    "
                f"Layout: {s.layout_name}    {in_key_str}    Oct: {s.octave_offset:+d}")
        draw.text((10, 6), text, fill=TEXT, font=self._font)

        # Page indicator
        if s.is_settings_page:
            page_label = "Settings"
        else:
            page_label = f"Scales {s.page + 1}/{SCALE_PAGES}"
        page_text = f"{page_label}  [{s.page + 1}/{TOTAL_PAGES}]"
        draw.text((WIDTH - 170, 8), page_text, fill=TEXT_DIM, font=self._font_small)

    def _draw_root_row(self, draw: ImageDraw.Draw, s: ScaleState) -> None:
        """Upper row: root note selection (8 slots)."""
        y_top = 35
        y_bot = 80

        for i in range(8):
            x = i * COL_W
            if i >= 12:
                continue

            name = ROOT_NAMES[i]
            is_selected = i == s.root

            if is_selected:
                draw.rectangle([x + 2, y_top, x + COL_W - 2, y_bot],
                               fill=ROOT_SELECTED_BG)

            color = TEXT if is_selected else TEXT_DIM
            bbox = draw.textbbox((0, 0), name, font=self._font_small)
            tw = bbox[2] - bbox[0]
            tx = x + (COL_W - tw) // 2
            draw.text((tx, y_top + 10), name, fill=color, font=self._font_small)

    def _draw_scale_row(self, draw: ImageDraw.Draw, s: ScaleState) -> None:
        """Lower row: scale type selection (8 per page)."""
        y_top = 90
        y_bot = 155
        page_offset = s.page * 8

        for i in range(8):
            scale_idx = page_offset + i
            x = i * COL_W

            if scale_idx >= len(SCALE_LIST):
                continue

            name = SCALE_LIST[scale_idx]
            is_selected = name == s.scale_name

            if is_selected:
                draw.rectangle([x + 2, y_top, x + COL_W - 2, y_bot],
                               fill=SCALE_SELECTED_BG)

            color = TEXT if is_selected else TEXT_DIM
            bbox = draw.textbbox((0, 0), name, font=self._font_small)
            tw = bbox[2] - bbox[0]
            tx = x + (COL_W - tw) // 2
            draw.text((tx, y_top + 18), name, fill=color, font=self._font_small)

    def _draw_settings_row(self, draw: ImageDraw.Draw, s: ScaleState) -> None:
        """Lower row: settings page (layouts + In Key toggle)."""
        y_top = 90
        y_bot = 155

        # Layout buttons
        for i, name in enumerate(LAYOUT_LIST):
            x = i * COL_W
            is_selected = name == s.layout_name

            if is_selected:
                draw.rectangle([x + 2, y_top, x + COL_W - 2, y_bot],
                               fill=LAYOUT_SELECTED_BG)

            color = TEXT if is_selected else TEXT_DIM
            bbox = draw.textbbox((0, 0), name, font=self._font_small)
            tw = bbox[2] - bbox[0]
            tx = x + (COL_W - tw) // 2
            draw.text((tx, y_top + 18), name, fill=color, font=self._font_small)

        # In Key toggle on last button (index 7)
        x = 7 * COL_W
        in_key_bg = (20, 80, 20) if s.in_key else (40, 40, 40)
        draw.rectangle([x + 2, y_top, x + COL_W - 2, y_bot], fill=in_key_bg)

        label = "In Key"
        bbox = draw.textbbox((0, 0), label, font=self._font_small)
        tw = bbox[2] - bbox[0]
        tx = x + (COL_W - tw) // 2
        draw.text((tx, y_top + 12), label, fill=TEXT, font=self._font_small)

        state_text = "ON" if s.in_key else "OFF"
        bbox2 = draw.textbbox((0, 0), state_text, font=self._font_tiny)
        tw2 = bbox2[2] - bbox2[0]
        tx2 = x + (COL_W - tw2) // 2
        draw.text((tx2, y_top + 32), state_text, fill=TEXT_DIM, font=self._font_tiny)
