import json
import os

from dotenv import load_dotenv

from . import DEFAULT_VERSION
from .debug import dbg
from .paths import CONFIG_FILE, THEMES_FILE

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
            cfg = json.loads(CONFIG_FILE.read_text())
            # Migrate legacy global "draft" key
            if "draft" in cfg:
                cfg.pop("draft", None)
                dbg("dropped legacy global draft")
            _CONFIG_CACHE = cfg
            return _CONFIG_CACHE
        except (json.JSONDecodeError, OSError) as e:
            dbg("config load failed", str(e))
    _CONFIG_CACHE = {
        "autosend": "",
        "version": DEFAULT_VERSION,
        "theme": "default",
        "notifications": True,
        "drafts": {},
        "clipboard": "auto",
    }
    return _CONFIG_CACHE


def save_config(cfg: dict):
    global _CONFIG_CACHE
    _CONFIG_CACHE = cfg
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    dbg("config saved", list(cfg.keys()))


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


def get_notifications() -> bool:
    return bool(load_config().get("notifications", True))


def set_notifications(on: bool):
    cfg = load_config()
    cfg["notifications"] = bool(on)
    save_config(cfg)


def get_draft(chat_id: str) -> str:
    return load_config().get("drafts", {}).get(chat_id, "")


def set_draft(chat_id: str, text: str):
    cfg = load_config()
    drafts = cfg.setdefault("drafts", {})
    if text.strip():
        drafts[chat_id] = text
    else:
        drafts.pop(chat_id, None)
    save_config(cfg)


def clear_draft(chat_id: str):
    set_draft(chat_id, "")


def prune_drafts(valid_chat_ids: set[str]):
    """Remove drafts for chats that no longer exist."""
    cfg = load_config()
    drafts = cfg.get("drafts", {})
    removed = [cid for cid in drafts if cid not in valid_chat_ids]
    if not removed:
        return
    for cid in removed:
        drafts.pop(cid, None)
    cfg["drafts"] = drafts
    save_config(cfg)
    dbg("drafts pruned", len(removed))


def get_clipboard() -> str:
    """auto | osc52 | stdout"""
    return load_config().get("clipboard", "auto")


def set_clipboard(mode: str):
    cfg = load_config()
    cfg["clipboard"] = mode
    save_config(cfg)


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
    global _THEMES_CACHE
    _THEMES_CACHE = None
    dbg("themes cache invalidated")