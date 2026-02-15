"""Push 2 pad matrix management with musical note grid."""

import logging

from push2.scales import ScaleState

log = logging.getLogger("push2reaper.push2.pads")

COLOR_HIGHLIGHT = "white"  # pressed pad


class PadManager:
    """Manages the 8x8 pad grid colors and state."""

    ROWS = 8
    COLS = 8

    def __init__(self, push, scale_state: ScaleState | None = None):
        self._push = push
        self._scale = scale_state or ScaleState()
        self._colors: list[list[str]] = [
            ["black"] * self.COLS for _ in range(self.ROWS)
        ]
        self._grid_colors: list[list[str]] = [
            ["black"] * self.COLS for _ in range(self.ROWS)
        ]

    def set_color(self, row: int, col: int, color: str) -> None:
        if self._colors[row][col] == color:
            return
        self._push.pads.set_pad_color((row, col), color)
        self._colors[row][col] = color

    def set_all(self, color: str) -> None:
        self._push.pads.set_all_pads_to_color(color)
        self._colors = [[color] * self.COLS for _ in range(self.ROWS)]

    def clear(self) -> None:
        self.set_all("black")

    def invalidate_cache(self) -> None:
        """Clear the color dedup cache so the next rebuild repaints all pads."""
        self._colors = [[""] * self.COLS for _ in range(self.ROWS)]

    def rebuild_grid(self) -> None:
        """Recalculate and repaint pad colors from current scale state."""
        for r in range(self.ROWS):
            for c in range(self.COLS):
                note = self._scale.pad_note(r, c)
                color = self._scale.note_color(note)
                self._grid_colors[r][c] = color
                self.set_color(r, c, color)
        log.info("Pad grid: %s %s (oct=%+d)",
                 self._scale.root_name, self._scale.scale_name,
                 self._scale.octave_offset)

    def init_default_layout(self) -> None:
        """Set initial pad colors — note grid with scale highlighting."""
        self.rebuild_grid()

    def highlight_pad(self, row: int, col: int) -> None:
        """Highlight a pad on press."""
        self.set_color(row, col, COLOR_HIGHLIGHT)

    def restore_pad(self, row: int, col: int) -> None:
        """Restore pad to its note grid color after release."""
        self.set_color(row, col, self._grid_colors[row][col])
