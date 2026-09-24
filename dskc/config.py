import json
import os
from dotenv import load_dotenv
from . import DEFAULT_VERSION
from .paths import CONFIG_FILE, THEMES_FILE

load_dotenv()


def get_token() -> str | None:
    return os.getenv("DEEPSEEK_TOKEN")


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"autosend": "", "version": DEFAULT_VERSION, "theme": "default"}


def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


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


def load_themes() -> dict:
    if THEMES_FILE.exists():
        try:
            data = json.loads(THEMES_FILE.read_text())
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    from .themes import BUILTIN_THEME
    return {"default": dict(BUILTIN_THEME)}