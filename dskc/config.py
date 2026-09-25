import json
import os

from dotenv import load_dotenv

from . import DEFAULT_VERSION
from .debug import dbg
from .paths import CONFIG_FILE, THEMES_FILE

load_dotenv()

_CONFIG_CACHE = None
_THEMES_CACHE = None


# ---------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------

def get_token() -> str | None:
    return os.getenv("DEEPSEEK_TOKEN")


# ---------------------------------------------------------------------
# Config file (config.json)
# ---------------------------------------------------------------------

def load_config() -> dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    if CONFIG_FILE.exists():
        try:
            _CONFIG_CACHE = json.loads(CONFIG_FILE.read_text())
            dbg("config loaded", list(_CONFIG_CACHE.keys()), once=True)
            return _CONFIG_CACHE
        except (json.JSONDecodeError, OSError) as e:
            dbg("config load failed", str(e))
    _CONFIG_CACHE = {
        "autosend": "",
        "version": DEFAULT_VERSION,
        "theme": "default",
    }
    return _CONFIG_CACHE


def save_config(cfg: dict):
    global _CONFIG_CACHE
    _CONFIG_CACHE = cfg
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    dbg("config saved", list(cfg.keys()))


# ---------------------------------------------------------------------
# Individual settings
# ---------------------------------------------------------------------

def get_autosend() -> str:
    return load_config().get("autosend", "")


def set_autosend(text: str):
    cfg = load_config()
    cfg["autosend"] = text
    save_config(cfg)


def get_version() -> str:
    return load_config().get("version", DEFAULT_VERSION)


def set_version(text: str):
    cfg = load_config()
    cfg["version"] = text
    save_config(cfg)


def get_theme_name() -> str:
    return load_config().get("theme", "default")


def set_theme_name(name: str):
    cfg = load_config()
    cfg["theme"] = name
    save_config(cfg)


# ---------------------------------------------------------------------
# Themes file (themes.json)
# ---------------------------------------------------------------------

def load_themes() -> dict:
    global _THEMES_CACHE
    if _THEMES_CACHE is not None:
        return _THEMES_CACHE
    if THEMES_FILE.exists():
        try:
            data = json.loads(THEMES_FILE.read_text())
            if isinstance(data, dict):
                _THEMES_CACHE = data
                dbg("themes loaded", list(data.keys()), once=True)
                return data
        except (json.JSONDecodeError, OSError) as e:
            dbg("themes load failed", str(e))
    from .themes import BUILTIN_THEME
    _THEMES_CACHE = {"default": dict(BUILTIN_THEME)}
    return _THEMES_CACHE


def reload_themes():
    """Force a re-read of themes.json on the next load_themes() call."""
    global _THEMES_CACHE
    _THEMES_CACHE = None
    dbg("themes cache invalidated")