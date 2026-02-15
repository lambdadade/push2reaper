"""Push 2 encoder handling."""

import logging
import push2_python.constants as c

log = logging.getLogger("push2reaper.push2.encoders")

# Encoder constants in order (left to right above the display)
TRACK_ENCODERS = [
    c.ENCODER_TRACK1_ENCODER,
    c.ENCODER_TRACK2_ENCODER,
    c.ENCODER_TRACK3_ENCODER,
    c.ENCODER_TRACK4_ENCODER,
    c.ENCODER_TRACK5_ENCODER,
    c.ENCODER_TRACK6_ENCODER,
    c.ENCODER_TRACK7_ENCODER,
    c.ENCODER_TRACK8_ENCODER,
]

# Map encoder constant → track index (0-7)
ENCODER_TO_INDEX = {enc: i for i, enc in enumerate(TRACK_ENCODERS)}

# Special encoders
TEMPO_ENCODER = c.ENCODER_TEMPO_ENCODER
SWING_ENCODER = c.ENCODER_SWING_ENCODER
MASTER_ENCODER = c.ENCODER_MASTER_ENCODER


class EncoderManager:
    """Tracks encoder touch state and provides index mapping."""

    def __init__(self):
        self._touched: set[str] = set()

    def on_touch(self, encoder_name: str) -> None:
        self._touched.add(encoder_name)

    def on_release(self, encoder_name: str) -> None:
        self._touched.discard(encoder_name)

    def is_touched(self, encoder_name: str) -> bool:
        return encoder_name in self._touched

    @staticmethod
    def get_track_index(encoder_name: str) -> int | None:
        """Return 0-7 track index for a track encoder, or None."""
        return ENCODER_TO_INDEX.get(encoder_name)
