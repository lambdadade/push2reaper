"""Scale selection mode.

Provides UI for choosing scales, root notes, layouts, and in-key filtering.
Overlays on top of the previous mode — exiting returns to the mode that
was active before scale mode was entered.
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

import push2_python.constants as c
from PIL import Image

from modes.base import Mode
from push2.buttons import UPPER_ROW, LOWER_ROW
from push2.scales import SCALE_LIST, LAYOUT_LIST, TOTAL_PAGES
from ui.scale_screen import ScaleScreen

if TYPE_CHECKING:
    from main import Push2ReaperDaemon

log = logging.getLogger("push2reaper.modes.scale")


class ScaleMode(Mode):
    """Scale/root/layout selection overlay mode."""

    name = "scale"

    def __init__(self):
        self._screen = ScaleScreen()

    def enter(self, daemon: Push2ReaperDaemon) -> None:
        log.info("Scale mode ON")
        if daemon.push2.buttons:
            daemon.push2.buttons.set_color(c.BUTTON_SCALE, "white")
        self._update_scale_buttons(daemon)

    def exit(self, daemon: Push2ReaperDaemon) -> None:
        log.info("Scale mode OFF → %s %s",
                 daemon.scale_state.root_name, daemon.scale_state.scale_name)
        if daemon.push2.buttons:
            daemon.push2.buttons.set_color(c.BUTTON_SCALE, "dark_gray")
        if daemon.push2.pads:
            daemon.push2.pads.rebuild_grid()

    def on_button(self, daemon: Push2ReaperDaemon, button: str, name: str) -> bool:
        # Upper row: select root note (same on all pages)
        if button in UPPER_ROW:
            idx = UPPER_ROW.index(button)
            if idx < 12:
                daemon.scale_state.set_root(idx)
                if daemon.push2.pads:
                    daemon.push2.pads.rebuild_grid()
                self._update_scale_buttons(daemon)
                log.info("Root → %s", daemon.scale_state.root_name)
            return True

        # Lower row: depends on current page
        if button in LOWER_ROW:
            idx = LOWER_ROW.index(button)
            if daemon.scale_state.is_settings_page:
                # Settings page: layouts on first buttons, In Key on last
                if idx < len(LAYOUT_LIST):
                    daemon.scale_state.set_layout(LAYOUT_LIST[idx])
                    if daemon.push2.pads:
                        daemon.push2.pads.rebuild_grid()
                    self._update_scale_buttons(daemon)
                    log.info("Layout → %s", daemon.scale_state.layout_name)
                elif idx == 7:  # In Key toggle
                    daemon.scale_state.in_key = not daemon.scale_state.in_key
                    if daemon.push2.pads:
                        daemon.push2.pads.rebuild_grid()
                    self._update_scale_buttons(daemon)
                    log.info("In Key → %s", daemon.scale_state.in_key)
            else:
                # Scale page: select scale
                scale_idx = daemon.scale_state.page * 8 + idx
                if scale_idx < len(SCALE_LIST):
                    daemon.scale_state.set_scale(SCALE_LIST[scale_idx])
                    if daemon.push2.pads:
                        daemon.push2.pads.rebuild_grid()
                    self._update_scale_buttons(daemon)
                    log.info("Scale → %s", daemon.scale_state.scale_name)
            return True

        # Page left/right: cycle through all pages (scales + layout)
        if button == c.BUTTON_PAGE_LEFT:
            daemon.scale_state.page = max(0, daemon.scale_state.page - 1)
            self._update_scale_buttons(daemon)
            return True
        if button == c.BUTTON_PAGE_RIGHT:
            daemon.scale_state.page = min(TOTAL_PAGES - 1,
                                           daemon.scale_state.page + 1)
            self._update_scale_buttons(daemon)
            return True

        # Octave buttons work in scale mode too
        if button == c.BUTTON_OCTAVE_UP:
            daemon.scale_state.octave_up()
            if daemon.push2.pads:
                daemon.push2.pads.rebuild_grid()
            log.info("Octave up → base note %d", daemon.scale_state.base_note)
            return True
        if button == c.BUTTON_OCTAVE_DOWN:
            daemon.scale_state.octave_down()
            if daemon.push2.pads:
                daemon.push2.pads.rebuild_grid()
            log.info("Octave down → base note %d", daemon.scale_state.base_note)
            return True

        # Any other button: exit scale mode (daemon handles this via the
        # return value of False — daemon will switch mode and re-dispatch)
        return False

    def render(self, daemon: Push2ReaperDaemon) -> Image.Image:
        return self._screen.render(daemon.scale_state)

    def _update_scale_buttons(self, daemon: Push2ReaperDaemon) -> None:
        """Light up buttons for scale selection mode."""
        if not daemon.push2.buttons:
            return

        # Upper row: root notes (C=0 through G=7) — same on all pages
        for i, btn in enumerate(UPPER_ROW):
            if i >= 12:
                daemon.push2.buttons.set_color(btn, "black")
            elif i == daemon.scale_state.root:
                daemon.push2.buttons.set_color(btn, "blue")
            else:
                daemon.push2.buttons.set_color(btn, "white")

        # Lower row: depends on current page
        if daemon.scale_state.is_settings_page:
            # Settings page: layouts + In Key toggle on last button
            for i, btn in enumerate(LOWER_ROW):
                if i < len(LAYOUT_LIST):
                    if LAYOUT_LIST[i] == daemon.scale_state.layout_name:
                        daemon.push2.buttons.set_color(btn, "orange")
                    else:
                        daemon.push2.buttons.set_color(btn, "white")
                elif i == 7:  # In Key toggle
                    color = "green" if daemon.scale_state.in_key else "dark_gray"
                    daemon.push2.buttons.set_color(btn, color)
                else:
                    daemon.push2.buttons.set_color(btn, "black")
        else:
            # Scale pages
            page_offset = daemon.scale_state.page * 8
            for i, btn in enumerate(LOWER_ROW):
                scale_idx = page_offset + i
                if scale_idx >= len(SCALE_LIST):
                    daemon.push2.buttons.set_color(btn, "black")
                elif SCALE_LIST[scale_idx] == daemon.scale_state.scale_name:
                    daemon.push2.buttons.set_color(btn, "turquoise")
                else:
                    daemon.push2.buttons.set_color(btn, "white")
