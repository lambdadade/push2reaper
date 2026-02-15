"""Application-level state manager — stub for Phase 2+."""


class StateManager:
    """Coordinates state between Reaper and Push 2 display."""

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
