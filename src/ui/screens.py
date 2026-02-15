"""Display screen definitions.

Each screen renders a PIL Image (960x160) for the Push 2 display.
"""

import logging
from PIL import Image, ImageDraw, ImageFont

from reaper.state import ReaperState, TrackInfo

log = logging.getLogger("push2reaper.ui.screens")

WIDTH = 960
HEIGHT = 160
STRIP_W = WIDTH // 8  # 120px per channel strip

# Colors
BG = (0, 0, 0)
TEXT = (220, 220, 220)
TEXT_DIM = (120, 120, 120)
ACCENT = (255, 120, 0)
FADER_BG = (40, 40, 40)
FADER_BORDER = (80, 80, 80)
MUTE_COLOR = (255, 60, 60)
SOLO_COLOR = (255, 220, 50)
REC_COLOR = (255, 40, 40)
SELECT_COLOR = (255, 140, 30)
PAN_COLOR = (100, 180, 255)
SEPARATOR = (50, 50, 50)

TRACK_COLORS = [
    (255, 60, 60),    # red
    (255, 140, 30),   # orange
    (255, 220, 50),   # yellow
    (50, 200, 80),    # green
    (50, 200, 200),   # turquoise
    (60, 100, 255),   # blue
    (160, 80, 220),   # purple
    (240, 100, 180),  # pink
]


class MixerScreen:
    """Renders an 8-channel mixer view."""

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
        """Render the mixer screen."""
        img = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(img)

        tracks = state.get_bank_tracks()

        for i, track in enumerate(tracks):
            x = i * STRIP_W
            color = track.color if track.color else TRACK_COLORS[i % len(TRACK_COLORS)]
            self._draw_channel_strip(draw, x, track, color, state)

        # Draw transport bar at bottom
        self._draw_transport_bar(draw, state)

        return img

    def _draw_channel_strip(
        self, draw: ImageDraw.ImageDraw, x: int, track: TrackInfo,
        color: tuple, state: ReaperState
    ) -> None:
        """Draw a single channel strip (120px wide)."""
        cx = x + STRIP_W // 2  # center x
        is_selected = track.index == state.selected_track

        # --- Header: track name (top 22px) ---
        header_color = color if is_selected else tuple(c // 2 for c in color)
        draw.rectangle([x, 0, x + STRIP_W - 2, 20], fill=header_color)

        name = track.name[:10]  # truncate long names
        draw.text(
            (cx, 10), name,
            fill=(0, 0, 0) if is_selected else (200, 200, 200),
            font=self._font_small, anchor="mm",
        )

        # --- Volume fader (main visual element) ---
        fader_x = x + 8
        fader_w = 30
        fader_top = 26
        fader_bottom = 120

        # Fader background
        draw.rectangle(
            [fader_x, fader_top, fader_x + fader_w, fader_bottom],
            fill=FADER_BG, outline=FADER_BORDER,
        )

        # Fader fill
        fader_h = fader_bottom - fader_top
        fill_h = int(track.volume * fader_h)
        if fill_h > 0:
            fill_color = color if not track.mute else (80, 80, 80)
            draw.rectangle(
                [fader_x + 1, fader_bottom - fill_h, fader_x + fader_w - 1, fader_bottom - 1],
                fill=fill_color,
            )

        # Volume text
        draw.text(
            (fader_x + fader_w // 2, fader_bottom + 6),
            track.volume_str[:7],
            fill=TEXT_DIM, font=self._font_tiny, anchor="mt",
        )

        # --- VU meter (thin bar next to fader) ---
        vu_x = fader_x + fader_w + 4
        vu_w = 6
        vu_h = int(track.vu * fader_h)
        if vu_h > 0:
            vu_color = (50, 200, 50) if track.vu < 0.8 else (255, 60, 60)
            draw.rectangle(
                [vu_x, fader_bottom - vu_h, vu_x + vu_w, fader_bottom],
                fill=vu_color,
            )

        # --- Pan indicator ---
        pan_x = x + 60
        pan_y = 35
        pan_w = 50
        # Pan line
        draw.rectangle([pan_x, pan_y, pan_x + pan_w, pan_y + 2], fill=FADER_BG)
        # Pan position dot
        dot_x = pan_x + int(track.pan * pan_w)
        draw.ellipse([dot_x - 3, pan_y - 3, dot_x + 3, pan_y + 3], fill=PAN_COLOR)
        # Pan text
        draw.text(
            (pan_x + pan_w // 2, pan_y + 10),
            track.pan_str[:5],
            fill=TEXT_DIM, font=self._font_tiny, anchor="mt",
        )

        # --- Mute/Solo/Rec indicators ---
        indicator_y = 60
        ind_size = 14

        # Mute
        if track.mute:
            draw.rectangle(
                [pan_x, indicator_y, pan_x + ind_size, indicator_y + ind_size],
                fill=MUTE_COLOR,
            )
            draw.text(
                (pan_x + ind_size // 2, indicator_y + ind_size // 2),
                "M", fill=(0, 0, 0), font=self._font_tiny, anchor="mm",
            )
        else:
            draw.rectangle(
                [pan_x, indicator_y, pan_x + ind_size, indicator_y + ind_size],
                outline=FADER_BORDER,
            )
            draw.text(
                (pan_x + ind_size // 2, indicator_y + ind_size // 2),
                "M", fill=TEXT_DIM, font=self._font_tiny, anchor="mm",
            )

        # Solo
        solo_x = pan_x + ind_size + 4
        if track.solo:
            draw.rectangle(
                [solo_x, indicator_y, solo_x + ind_size, indicator_y + ind_size],
                fill=SOLO_COLOR,
            )
            draw.text(
                (solo_x + ind_size // 2, indicator_y + ind_size // 2),
                "S", fill=(0, 0, 0), font=self._font_tiny, anchor="mm",
            )
        else:
            draw.rectangle(
                [solo_x, indicator_y, solo_x + ind_size, indicator_y + ind_size],
                outline=FADER_BORDER,
            )
            draw.text(
                (solo_x + ind_size // 2, indicator_y + ind_size // 2),
                "S", fill=TEXT_DIM, font=self._font_tiny, anchor="mm",
            )

        # Rec arm
        rec_x = solo_x + ind_size + 4
        if track.rec_arm:
            draw.ellipse(
                [rec_x, indicator_y, rec_x + ind_size, indicator_y + ind_size],
                fill=REC_COLOR,
            )
        else:
            draw.ellipse(
                [rec_x, indicator_y, rec_x + ind_size, indicator_y + ind_size],
                outline=FADER_BORDER,
            )

        # --- Separator line ---
        draw.line([x + STRIP_W - 1, 0, x + STRIP_W - 1, HEIGHT], fill=SEPARATOR)

    def _draw_transport_bar(self, draw: ImageDraw.ImageDraw, state: ReaperState) -> None:
        """Draw transport info bar at bottom."""
        bar_y = HEIGHT - 18

        # Background
        draw.rectangle([0, bar_y, WIDTH, HEIGHT], fill=(20, 20, 20))

        # Transport state
        if state.recording:
            status = "REC"
            status_color = REC_COLOR
        elif state.playing:
            status = "PLAY"
            status_color = (50, 200, 80)
        elif state.paused:
            status = "PAUSE"
            status_color = ACCENT
        else:
            status = "STOP"
            status_color = TEXT_DIM

        draw.text((8, bar_y + 9), status, fill=status_color, font=self._font_small, anchor="lm")

        # Beat position
        draw.text(
            (100, bar_y + 9), state.beat_str,
            fill=TEXT, font=self._font_small, anchor="lm",
        )

        # Tempo
        draw.text(
            (250, bar_y + 9), f"{state.tempo:.1f} BPM",
            fill=TEXT_DIM, font=self._font_small, anchor="lm",
        )

        # Repeat indicator
        if state.repeat:
            draw.text(
                (400, bar_y + 9), "LOOP",
                fill=ACCENT, font=self._font_small, anchor="lm",
            )

        # Bank info
        bank_start = state.bank_offset + 1
        bank_end = state.bank_offset + 8
        draw.text(
            (WIDTH - 8, bar_y + 9),
            f"Tracks {bank_start}-{bank_end}",
            fill=TEXT_DIM, font=self._font_small, anchor="rm",
        )
