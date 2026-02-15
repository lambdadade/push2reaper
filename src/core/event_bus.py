import logging
import threading
from typing import Any, Callable

log = logging.getLogger("push2reaper.event_bus")


class EventBus:
    """Thread-safe publish/subscribe event system.

    Decouples Push 2 hardware events from Reaper communication
    and display rendering.
    """

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, callback: Callable) -> None:
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
            log.debug("Subscribed to '%s': %s", event_type, callback.__name__)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [
                    cb for cb in self._subscribers[event_type] if cb is not callback
                ]

    def publish(self, event_type: str, data: Any = None) -> None:
        with self._lock:
            callbacks = list(self._subscribers.get(event_type, []))

        for callback in callbacks:
            try:
                callback(data)
            except Exception:
                log.exception(
                    "Error in event handler for '%s': %s",
                    event_type,
                    callback.__name__,
                )
