"""Musical scale definitions and state for Push 2 pad grid."""

import logging

log = logging.getLogger("push2reaper.push2.scales")

# Scale definitions: name -> tuple of semitone offsets from root
SCALES = {
    "Major":          (0, 2, 4, 5, 7, 9, 11),
    "Minor":          (0, 2, 3, 5, 7, 8, 10),
    "Dorian":         (0, 2, 3, 5, 7, 9, 10),
    "Mixolydian":     (0, 2, 4, 5, 7, 9, 10),
    "Lydian":         (0, 2, 4, 6, 7, 9, 11),
    "Phrygian":       (0, 1, 3, 5, 7, 8, 10),
    "Locrian":        (0, 1, 3, 5, 6, 8, 10),
    "Harm. Minor":    (0, 2, 3, 5, 7, 8, 11),
    "Mel. Minor":     (0, 2, 3, 5, 7, 9, 11),
    "Penta. Maj":     (0, 2, 4, 7, 9),
    "Penta. Min":     (0, 3, 5, 7, 10),
    "Blues":           (0, 3, 5, 6, 7, 10),
    "Whole Tone":     (0, 2, 4, 6, 8, 10),
    "Diminished":     (0, 2, 3, 5, 6, 8, 9, 11),
    "Hungarian Min":  (0, 2, 3, 6, 7, 8, 11),
    "Spanish":        (0, 1, 4, 5, 7, 9, 10),
}

SCALE_LIST = list(SCALES.keys())

ROOT_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Layout definitions: name -> row interval in semitones
# Push 2 hardware always sends 8 semitones between rows, but we use layouts
# to define the *virtual* note grid for coloring and note remapping.
LAYOUTS = {
    "4th":     5,   # perfect 4th (Ableton default)
    "3rd":     4,   # major 3rd
    "Sequent": 1,   # sequential (chromatic left-to-right, row-by-row)
}
LAYOUT_LIST = list(LAYOUTS.keys())

# Total pages in scale mode
SCALE_PAGES = (len(SCALE_LIST) + 7) // 8  # ceil division
TOTAL_PAGES = SCALE_PAGES + 1  # last page is settings


class ScaleState:
    """Holds the current musical scale configuration."""

    def __init__(self):
        self.root: int = 0              # 0=C, 1=C#, ... 11=B
        self.scale_name: str = "Major"
        self.layout_name: str = "4th"   # row interval layout
        self.octave_offset: int = 0     # shifts base_note by ±12
        self.page: int = 0              # current page in scale mode
        self.in_key: bool = False       # hide chromatic notes (black LEDs)

    @property
    def scale_intervals(self) -> tuple[int, ...]:
        return SCALES[self.scale_name]

    @property
    def scale_notes(self) -> set[int]:
        """Set of semitone values (0-11) in the current scale."""
        return {(self.root + iv) % 12 for iv in self.scale_intervals}

    @property
    def root_name(self) -> str:
        return ROOT_NAMES[self.root]

    @property
    def base_note(self) -> int:
        """Bottom-left pad virtual note, shifted by root and octave.

        Like DrivenByMoss: startNote + root_offset + octave * 12.
        Changing root shifts the entire grid so the bottom-left pad
        starts on the selected root note.
        """
        return 36 + self.root + self.octave_offset * 12

    @property
    def row_interval(self) -> int:
        """Semitones between rows based on current layout."""
        return LAYOUTS.get(self.layout_name, 5)

    @property
    def is_settings_page(self) -> bool:
        """True if the current page is the settings page."""
        return self.page >= SCALE_PAGES

    def pad_note(self, row: int, col: int) -> int:
        """Virtual MIDI note for a pad position based on layout.

        This determines the note each pad *represents* (for coloring and
        note remapping).  The hardware always sends 8 semitones between
        rows, but we remap to the chosen layout interval.
        """
        return self.base_note + (7 - row) * self.row_interval + col

    def note_color(self, midi_note: int) -> str:
        """Determine pad color based on scale membership."""
        semitone = midi_note % 12
        if semitone == self.root:
            return "blue"
        elif semitone in self.scale_notes:
            return "turquoise"
        else:
            return "black" if self.in_key else "dark_gray"

    def hardware_note(self, row: int, col: int) -> int:
        """Raw MIDI note the hardware sends for this pad position.

        Push 2: (0,0)=top-left=92, (7,0)=bottom-left=36.
        """
        return 92 - row * 8 + col

    def build_note_table(self) -> dict[int, int]:
        """Build hardware-note -> virtual-note translation table.

        Like DrivenByMoss's getNoteMatrix(): maps each raw hardware MIDI
        note to the virtual note determined by the current layout.
        """
        table = {}
        for row in range(8):
            for col in range(8):
                hw = self.hardware_note(row, col)
                virtual = self.pad_note(row, col)
                if 0 <= virtual <= 127:
                    table[hw] = virtual
        return table

    def set_root(self, root: int) -> None:
        self.root = root % 12

    def set_scale(self, name: str) -> None:
        if name in SCALES:
            self.scale_name = name

    def set_layout(self, name: str) -> None:
        if name in LAYOUTS:
            self.layout_name = name

    def octave_up(self) -> None:
        if self.base_note + 12 <= 108:
            self.octave_offset += 1

    def octave_down(self) -> None:
        if self.base_note - 12 >= 0:
            self.octave_offset -= 1
