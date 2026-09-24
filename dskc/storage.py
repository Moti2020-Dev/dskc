import datetime
import json
from .paths import CHATS_FILE, HISTORY_DIR


def load_chats() -> dict:
    if CHATS_FILE.exists():
        try:
            return json.loads(CHATS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {"chats": {}}
    return {"chats": {}}


def save_chats(data: dict):
    CHATS_FILE.write_text(json.dumps(data, indent=2))


def update_chat(chat_id: str, title: str | None = None,
                parent_message_id: int | None = None):
    stored = load_chats()
    chats = stored.setdefault("chats", {})
    entry = chats.setdefault(chat_id, {})
    if title is not None:
        entry["title"] = title
    if parent_message_id is not None:
        entry["parent_message_id"] = parent_message_id
    entry["last_used"] = datetime.datetime.now().isoformat()
    save_chats(stored)


def delete_chat(chat_id: str):
    stored = load_chats()
    stored.get("chats", {}).pop(chat_id, None)
    save_chats(stored)


def _history_path(chat_id: str):
    return HISTORY_DIR / f"{chat_id}.json"


def append_history(chat_id: str, role: str, content: str):
    p = _history_path(chat_id)
    if p.exists():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            data = {"chat_id": chat_id, "messages": []}
    else:
        data = {"chat_id": chat_id, "messages": []}
    data["messages"].append({
        "role": role,
        "content": content,
        "at": datetime.datetime.now().isoformat(),
    })
    p.write_text(json.dumps(data, indent=2))


def load_history(chat_id: str) -> dict | None:
    p = _history_path(chat_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None