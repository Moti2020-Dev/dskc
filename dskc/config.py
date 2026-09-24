import os
from dotenv import load_dotenv

load_dotenv()


_CONFIG_CACHE = None
_THEMES_CACHE = None

def get_token() -> str | None:
    return os.getenv("DEEPSEEK_TOKEN")

def load_config() -> dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    if CONFIG_FILE.exists():
        try:
            _CONFIG_CACHE = json.loads(CONFIG_FILE.read_text())
            dbg("config loaded", list(_CONFIG_CACHE.keys()))
            return _CONFIG_CACHE
        except (json.JSONDecodeError, OSError) as e:
            dbg("config load failed", str(e))
    _CONFIG_CACHE = {"autosend": "", "version": DEFAULT_VERSION, "theme": "default"}
    return _CONFIG_CACHE


def save_config(cfg: dict):
    global _CONFIG_CACHE
    _CONFIG_CACHE = cfg
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    dbg("config saved", list(cfg.keys()))


def load_themes() -> dict:
    global _THEMES_CACHE
    if _THEMES_CACHE is not None:
        return _THEMES_CACHE
    if THEMES_FILE.exists():
        try:
            data = json.loads(THEMES_FILE.read_text())
            if isinstance(data, dict):
                _THEMES_CACHE = data
                dbg("themes loaded", list(data.keys()), True)
                return data
        except (json.JSONDecodeError, OSError) as e:
            dbg("themes load failed", str(e))
    from .themes import BUILTIN_THEME
    _THEMES_CACHE = {"default": dict(BUILTIN_THEME)}
    return _THEMES_CACHE