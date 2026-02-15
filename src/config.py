import os
import logging
from pathlib import Path

import yaml
from dotenv import load_dotenv

log = logging.getLogger("push2reaper.config")

# Project root is one level up from src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file with .env overrides."""
    load_dotenv(PROJECT_ROOT / ".env")

    yaml_path = Path(config_path) if config_path else CONFIG_DIR / "default_mappings.yaml"
    if not yaml_path.exists():
        log.warning("Config file not found: %s — using defaults", yaml_path)
        config = {}
    else:
        with open(yaml_path) as f:
            config = yaml.safe_load(f) or {}

    # Environment variable overrides
    osc = config.setdefault("osc", {})
    osc["reaper_ip"] = os.environ.get("REAPER_OSC_IP", osc.get("reaper_ip", "127.0.0.1"))
    osc["reaper_port"] = int(os.environ.get("REAPER_OSC_PORT", osc.get("reaper_port", 8000)))
    osc["listen_port"] = int(os.environ.get("LISTEN_PORT", osc.get("listen_port", 9000)))

    p2 = config.setdefault("push2", {})
    p2["fps"] = int(os.environ.get("DISPLAY_FPS", p2.get("fps", 30)))

    log.info(
        "Config loaded — OSC to %s:%d, listen on :%d, display %d fps",
        osc["reaper_ip"],
        osc["reaper_port"],
        osc["listen_port"],
        p2["fps"],
    )
    return config
