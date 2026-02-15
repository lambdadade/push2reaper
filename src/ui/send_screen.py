"""Send level display screen.

Shows 8 send levels for the currently selected track, with
send names and volume bars.
"""

import logging
from PIL import Image, ImageDraw, ImageFont

from reaper.state import ReaperState

log = logging.getLogger("push2reaper.ui.send_screen")

WIDTH = 960
HEIGHT = 160
STRIP_W = WIDTH // 8  # 120px per send strip

BG = (0, 0, 0)
TEXT = (220, 220, 220)
TEXT_DIM = (120, 120, 120)
FADER_BG = (40, 40, 40)
FADER_BORDER = (80, 80, 80)
SEPARATOR = (50, 50, 50)
SEND_COLOR = (100, 180, 255)
HEADER_COLOR = (60, 100, 200)


class SendScreen:
    """Renders send levels for the selected track."""

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

    def render(self, state: ReaperState) -> Image.Image:
        img = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(img)

        track_num = state.selected_track
        track = state.tracks.get(track_num)
        if track is None:
            return img

        # Header: track name
        draw.rectangle([0, 0, WIDTH, 20], fill=(30, 30, 30))
        draw.text(
            (WIDTH // 2, 10),
            f"Sends: {track.name}",
            fill=TEXT, font=self._font, anchor="mm",
        )

        # Draw 8 send strips
        sends = track.sends
        for i in range(8):
            x = i * STRIP_W
            if i < len(sends):
                send = sends[i]
                self._draw_send_strip(draw, x, i, send)
            else:
                self._draw_empty_strip(draw, x, i)
            # Separator
            draw.line([x + STRIP_W - 1, 20, x + STRIP_W - 1, HEIGHT],
                      fill=SEPARATOR)

        return img

    def _draw_send_strip(self, draw: ImageDraw.ImageDraw, x: int,
                         idx: int, send: dict) -> None:
        cx = x + STRIP_W // 2

        # Send name
        name = send.get("name", f"Send {idx + 1}")[:12]
        draw.text((cx, 32), name, fill=TEXT, font=self._font_small, anchor="mm")

        # Volume fader
        fader_x = x + 35
        fader_w = 50
        fader_top = 44
        fader_bottom = 130

        draw.rectangle(
            [fader_x, fader_top, fader_x + fader_w, fader_bottom],
            fill=FADER_BG, outline=FADER_BORDER,
        )

        vol = send.get("volume", 0.0)
        fader_h = fader_bottom - fader_top
        fill_h = int(vol * fader_h)
        if fill_h > 0:
            draw.rectangle(
                [fader_x + 1, fader_bottom - fill_h,
                 fader_x + fader_w - 1, fader_bottom - 1],
                fill=SEND_COLOR,
            )

        # Volume text
        vol_str = send.get("volume_str", f"{vol:.0%}")[:8]
        draw.text(
            (cx, fader_bottom + 8), vol_str,
            fill=TEXT_DIM, font=self._font_tiny, anchor="mt",
        )

    def _draw_empty_strip(self, draw: ImageDraw.ImageDraw, x: int, idx: int) -> None:
        cx = x + STRIP_W // 2
        draw.text((cx, 80), "—", fill=TEXT_DIM, font=self._font_small, anchor="mm")
