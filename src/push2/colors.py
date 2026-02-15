"""Push 2 color palette management."""

import logging

log = logging.getLogger("push2reaper.push2.colors")

# Default colors available in push2-python
STOCK_COLORS = [
    "black", "orange", "yellow", "turquoise", "purple", "pink",
    "white", "light_gray", "dark_gray", "blue", "green", "red",
]

# Semantic colors for our UI
TRACK_COLORS = [
    "red", "orange", "yellow", "green", "turquoise", "blue", "purple", "pink",
]

# Transport button colors
TRANSPORT_COLORS = {
    "play_active": "green",
    "play_inactive": "dark_gray",
    "record_active": "red",
    "record_inactive": "dark_gray",
    "stop_active": "white",
    "stop_inactive": "dark_gray",
}


def get_track_color(track_index: int) -> str:
    """Get a color for a track by index (cycles through palette)."""
    return TRACK_COLORS[track_index % len(TRACK_COLORS)]


def setup_custom_palette(push):
    """Register any custom colors on the Push 2 hardware.

    Called once after hardware connection. Extend this to add
    custom RGB values beyond the stock palette.
    """
    log.debug("Using stock color palette")
