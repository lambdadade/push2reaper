import logging
import sys
import os


def setup_logging(level: str = None) -> logging.Logger:
    """Configure logging for the push2reaper daemon."""
    log_level = level or os.environ.get("LOG_LEVEL", "INFO")
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure our namespace logger
    root = logging.getLogger("push2reaper")
    root.setLevel(numeric_level)
    root.addHandler(handler)
    root.propagate = False  # prevent duplicate output via root logger

    # Also prevent the root logger from duplicating our messages
    logging.basicConfig(level=logging.WARNING)

    # Quiet noisy libraries
    for name in ("mido", "pyusb", "flask", "engineio", "socketio",
                 "pythonosc", "werkzeug"):
        logging.getLogger(name).setLevel(logging.WARNING)

    return root
