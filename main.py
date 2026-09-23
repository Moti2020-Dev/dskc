import asyncio
import os
import json
import uuid
import sys
import base64
import re
import pathlib
import datetime
import aiohttp
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.enums import EditingMode
from pow_solver import DeepSeekHash
from lib_color import Color, Markdown, RESET

load_dotenv()

DEFAULT_VERSION = "V1.2"
DEBUG = "--debug" in sys.argv

_HERE = pathlib.Path(__file__).resolve().parent
CHATS_FILE = _HERE / "chats.json"
CONFIG_FILE = _HERE / "config.json"
THEMES_FILE = _HERE / "themes.json"
HISTORY_DIR = _HERE / "history"
HISTORY_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------

_BUILTIN_THEME = {
    "banner": "100,200,255",
    "version": "200,225,100",
    "prompt": "100,200,255",
    "continuation": "110,110,110",
    "error": "255,80,80",
    "warning": "255,200,0",
    "success": "0,220,120",
    "info": "0,170,170",
    "dim": "120,120,120",
    "chat_num": "255,215,0",
    "chat_id": "110,110,110",
    "menu_action": "200,180,255",
    "menu_key": "180,180,180",
    "link": "100,200,255",
}


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
    return {"default": dict(_BUILTIN_THEME)}


def get_theme() -> dict:
    themes = load_themes()
    name = get_theme_name()
    base = themes.get("default", _BUILTIN_THEME)
    chosen = themes.get(name, base)
    merged = dict(_BUILTIN_THEME)
    merged.update(base)
    merged.update(chosen)
    return merged


def tag(name: str, text: str) -> str:
    """Apply a theme tag to text."""
    theme = get_theme()
    value = theme.get(name)
    if not value:
        return text
    try:
        r, g, b = (int(x.strip()) for x in value.split(","))
    except (ValueError, AttributeError):
        return text
    return f"{Color.Basic.fg(r, g, b)}{text}{RESET}"


_BANNER_GRADIENT = [
    (0x1a, 0x1a, 0x6e),
    (0x1a, 0x3a, 0x7e),
    (0x1a, 0x5a, 0x8e),
    (0x1a, 0x7a, 0x9e),
    (0x1a, 0x9a, 0xae),
    (0x1a, 0xba, 0xbe),
    (0x1a, 0xda, 0xce),
    (0x1a, 0xfa, 0xde),
]


def _gradient_text(text: str) -> str:
    """Color each visible character along the banner gradient."""
    stops = _BANNER_GRADIENT
    n = len(stops)
    visible = [i for i, ch in enumerate(text) if ch != " "]
    if not visible:
        return text
    out = []
    for i, ch in enumerate(text):
        if ch == " ":
            out.append(ch)
            continue
        # progress of this visible char among all visible chars
        pos = visible.index(i)
        t = pos / max(1, len(visible) - 1)
        idx = int(round(t * (n - 1)))
        r, g, b = stops[idx]
        out.append(f"{Color.Basic.fg(r, g, b)}{ch}")
    out.append(RESET)
    return "".join(out)

def show_banner():
    border = tag("dim", "▌")
    bar_top = tag("dim", "▛" + "▀" * 39)
    bar_bot = tag("dim", "▙" + "▄" * 39)

    line1 = _gradient_text("  ◆  D S K C  ·  D E E P S E E K  ")
    line2 = _gradient_text("     a command-line client         ")

    print()
    print(" " + bar_top)
    print(" " + border + line1 + tag("dim", "▐"))
    print(" " + border + line2 + tag("dim", "▐"))
    print(" " + bar_bot)
    print()

# ---------------------------------------------------------------------
# Chat storage
# ---------------------------------------------------------------------

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


# ---------------------------------------------------------------------
# Per-chat history (for export)
# ---------------------------------------------------------------------

def _history_path(chat_id: str) -> pathlib.Path:
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


def export_chat_markdown(chat_id: str) -> pathlib.Path | None:
    p = _history_path(chat_id)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    title = load_chats().get("chats", {}).get(chat_id, {}).get("title", chat_id)
    out_path = _HERE / f"export_{chat_id[:8]}.md"

    lines = [
        f"# {title}",
        "",
        f"- Chat ID: `{chat_id}`",
        f"- URL: https://chat.deepseek.com/a/chat/s/{chat_id}",
        f"- Exported: {datetime.datetime.now().isoformat()}",
        "",
        "---",
        "",
    ]
    for msg in data.get("messages", []):
        role = "You" if msg.get("role") == "user" else "DeepSeek"
        lines.append(f"### {role}")
        lines.append("")
        lines.append(msg.get("content", ""))
        lines.append("")

    out_path.write_text("\n".join(lines))
    return out_path


# ---------------------------------------------------------------------
# Custom color escapes
# ---------------------------------------------------------------------
#
#   \C:{preset}text       foreground preset
#   \B:{preset}text       background preset
#   \Cx{RRGGBB}text       foreground hex
#   \Bx{RRGGBB}text       background hex
#   \U:on                 underline on
#   \U:off                underline off
#   \R                    explicit reset
#
# Each color escape applies until the next escape or end of line.
# A reset is auto-appended at each newline.
# ---------------------------------------------------------------------

def _apply_custom(text: str) -> str:
    lines = text.split("\n")
    rendered_lines = [_apply_custom_line(line) + RESET for line in lines]
    return "\n".join(rendered_lines)


def _apply_custom_line(line: str) -> str:
    result = []
    i = 0
    n = len(line)
    while i < n:
        if line[i] == "\\" and i + 1 < n:
            if line.startswith("\\R", i):
                result.append(RESET)
                i += 2
                continue

            if line.startswith("\\U:on", i):
                result.append("\033[4m")
                i += 5
                continue

            if line.startswith("\\U:off", i):
                result.append("\033[24m")
                i += 6
                continue

            if line.startswith("\\Cx{", i):
                j = i + 4
                k = line.find("}", j)
                if k != -1 and k - j == 6 and all(
                    c in "0123456789abcdefABCDEF" for c in line[j:k]
                ):
                    value = int(line[j:k], 16)
                    r = (value >> 16) & 0xFF
                    g = (value >> 8) & 0xFF
                    b = value & 0xFF
                    result.append(Color.Basic.fg(r, g, b))
                    i = k + 1
                    continue

            if line.startswith("\\Bx{", i):
                j = i + 4
                k = line.find("}", j)
                if k != -1 and k - j == 6 and all(
                    c in "0123456789abcdefABCDEF" for c in line[j:k]
                ):
                    value = int(line[j:k], 16)
                    r = (value >> 16) & 0xFF
                    g = (value >> 8) & 0xFF
                    b = value & 0xFF
                    result.append(Color.Basic.bg(r, g, b))
                    i = k + 1
                    continue

            if line.startswith("\\C:{", i):
                j = i + 4
                k = line.find("}", j)
                if k != -1:
                    preset = line[j:k].lower()
                    fn = getattr(Color.ColorPresets, preset, None)
                    if fn:
                        sentinel = "\x00"
                        wrapped = fn(sentinel)
                        if sentinel in wrapped:
                            result.append(wrapped.split(sentinel)[0])
                    i = k + 1
                    continue

            if line.startswith("\\B:{", i):
                j = i + 4
                k = line.find("}", j)
                if k != -1:
                    preset = line[j:k].lower()
                    fn = getattr(Color.ColorPresets, preset, None)
                    if fn:
                        sentinel = "\x00"
                        wrapped = fn(sentinel)
                        if sentinel in wrapped:
                            prefix = wrapped.split(sentinel)[0]
                            prefix = prefix.replace("[38;2;", "[48;2;")
                            prefix = prefix.replace("[38;5;", "[48;5;")
                            result.append(prefix)
                    i = k + 1
                    continue

        result.append(line[i])
        i += 1
    return "".join(result)


def render_markdown(text: str) -> str:
    return Markdown.render(_apply_custom(text))


# ---------------------------------------------------------------------
# Title marker
# ---------------------------------------------------------------------

_TITLE_RE = re.compile(r"^\\\{([^}]*)\}\\\s*\n?", re.MULTILINE)


def extract_title(text: str) -> tuple[str | None, str]:
    m = _TITLE_RE.match(text)
    if m:
        return m.group(1).strip(), text[m.end():]
    return None, text


# ---------------------------------------------------------------------
# SSE / API
# ---------------------------------------------------------------------

def parse_sse_line(line: str):
    line = line.strip()
    if not line:
        return None
    if line.startswith("event:"):
        return ("event", line.split(":", 1)[1].strip())
    if line.startswith("data:"):
        payload = line.split(":", 1)[1].strip()
        if not payload:
            return None
        try:
            return ("data", json.loads(payload))
        except json.JSONDecodeError:
            return None
    return None


async def solve_pow(session, token, target_path="/api/v0/chat/completion"):
    async with session.post(
        "https://chat.deepseek.com/api/v0/chat/create_pow_challenge",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_path": target_path},
    ) as resp:
        data = await resp.json()
        challenge = data["data"]["biz_data"]["challenge"]

    solver = DeepSeekHash()
    answer = solver.calculate_hash(
        challenge["challenge"],
        challenge["salt"],
        challenge["difficulty"],
        challenge["expire_at"],
    )
    if answer is None:
        raise RuntimeError("PoW not solved")

    result = {
        "algorithm": challenge["algorithm"],
        "challenge": challenge["challenge"],
        "salt": challenge["salt"],
        "answer": int(answer),
        "signature": challenge["signature"],
        "target_path": target_path,
    }
    return base64.b64encode(json.dumps(result).encode()).decode()


async def create_chat_session(session, token) -> str:
    async with session.post(
        "https://chat.deepseek.com/api/v0/chat_session/create",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    ) as resp:
        data = await resp.json()
        if DEBUG:
            print(f"[DEBUG] create_chat_session raw: {json.dumps(data)[:500]}")
        try:
            return data["data"]["biz_data"]["chat_session"]["id"]
        except (KeyError, TypeError):
            biz = data.get("data", {}).get("biz_data", data)
            if isinstance(biz, dict):
                if "chat_session" in biz and isinstance(biz["chat_session"], dict):
                    return biz["chat_session"]["id"]
                if "id" in biz:
                    return biz["id"]
            raise ValueError(f"Could not find session ID. Response: {data}")


async def fetch_chat_title(session, token, chat_id: str) -> str | None:
    try:
        async with session.get(
            "https://chat.deepseek.com/api/v0/chat_session/fetch_page",
            headers={"Authorization": f"Bearer {token}"},
            params={"count": 50},
        ) as resp:
            data = await resp.json()
    except Exception:
        return None

    if DEBUG:
        print(f"[DEBUG] fetch_page raw: {json.dumps(data)[:500]}")

    try:
        sessions = data.get("data", {}).get("biz_data", {}).get("sessions", [])
    except AttributeError:
        return None

    for item in sessions:
        if item.get("id") == chat_id:
            return item.get("title")
    return None


async def send_message(session, token, prompt: str, chat_id: str,
                       parent_message_id: int | None = None):
    pow_response = await solve_pow(session, token)

    payload = {
        "chat_session_id": chat_id,
        "parent_message_id": parent_message_id,
        "prompt": prompt,
        "ref_file_ids": [],
        "thinking_enabled": False,
        "search_enabled": False,
    }

    content_parts: list[str] = []
    metadata = {}

    async with session.post(
        "https://chat.deepseek.com/api/v0/chat/completion",
        headers={
            "Authorization": f"Bearer {token}",
            "x-ds-pow-response": pow_response,
            "Content-Type": "application/json",
        },
        json=payload,
    ) as resp:
        async for raw_line in resp.content:
            line = raw_line.decode("utf-8", errors="ignore")
            parsed = parse_sse_line(line)
            if not parsed:
                continue

            kind, value = parsed
            if DEBUG:
                print(f"[DEBUG] {kind}: {json.dumps(value)[:200]}")

            if kind == "event":
                continue

            obj = value
            if not isinstance(obj, dict):
                continue

            if obj.get("o") == "APPEND" and obj.get("p") == "response/content":
                chunk = obj.get("v", "")
                if isinstance(chunk, str):
                    content_parts.append(chunk)
                continue

            if set(obj.keys()) == {"v"}:
                chunk = obj["v"]
                if isinstance(chunk, str):
                    content_parts.append(chunk)
                continue

            if obj.get("o") == "SET":
                continue

            if "v" in obj and isinstance(obj["v"], dict):
                inner = obj["v"].get("response")
                if inner and isinstance(inner.get("content"), str):
                    content_parts.append(inner["content"])
                if inner and isinstance(inner.get("message_id"), int):
                    metadata["response_message_id"] = inner["message_id"]
                continue

            for key in ("request_message_id", "response_message_id",
                        "model_type", "updated_at"):
                if key in obj:
                    metadata[key] = obj[key]

    return "".join(content_parts), metadata.get("response_message_id")


# ---------------------------------------------------------------------
# Menu sentinels + key bindings
# ---------------------------------------------------------------------

S_QUIT     = "\x00QUIT"
S_CANCEL   = "\x00CANCEL"
S_RENAME   = "\x00RENAME"
S_DELETE   = "\x00DELETE"
S_EXPORT   = "\x00EXPORT"
S_VERSION  = "\x00VERSION"
S_THEME    = "\x00THEME"
S_AUTOSEND = "\x00AUTOSEND"


def build_chat_session() -> PromptSession:
    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        event.current_buffer.validate_and_handle()

    @kb.add("c-o")
    def _(event):
        event.current_buffer.insert_text("\n")

    @kb.add("escape", "enter")
    def _(event):
        event.current_buffer.insert_text("\n")

    @kb.add("escape", eager=True)
    def _(event):
        event.app.exit(result=S_CANCEL)

    return PromptSession(
        key_bindings=kb,
        multiline=True,
        prompt_continuation=lambda width, line_number, is_soft_wrap: tag("continuation", "  | "),
        editing_mode=EditingMode.EMACS,
    )


def build_menu_session() -> PromptSession:
    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        event.current_buffer.validate_and_handle()

    @kb.add("c-o")
    def _(event):
        event.current_buffer.insert_text("\n")

    @kb.add("escape", eager=True)
    def _(event):
        event.app.exit(result=S_CANCEL)

    for key, sentinel in [
        ("r", S_RENAME), ("d", S_DELETE), ("x", S_EXPORT),
        ("v", S_VERSION), ("t", S_THEME),
        ("e", S_AUTOSEND), ("a", S_AUTOSEND),
        ("q", S_QUIT),
    ]:
        def make_handler(sent=sentinel):
            def handler(event):
                event.app.exit(result=sent)
            return handler
        kb.add(key)(make_handler())

    return PromptSession(
        key_bindings=kb,
        multiline=True,
        prompt_continuation=lambda width, line_number, is_soft_wrap: tag("continuation", "  | "),
        editing_mode=EditingMode.EMACS,
    )


CHAT_SESSION: PromptSession | None = None
MENU_SESSION: PromptSession | None = None


def get_chat_session() -> PromptSession:
    global CHAT_SESSION
    if CHAT_SESSION is None:
        CHAT_SESSION = build_chat_session()
    return CHAT_SESSION


def get_menu_session() -> PromptSession:
    global MENU_SESSION
    if MENU_SESSION is None:
        MENU_SESSION = build_menu_session()
    return MENU_SESSION


async def ask_multiline(label: str | None = None) -> str:
    session = get_chat_session()
    if label is None:
        label = tag("prompt", "Prompt: ")
    while True:
        text = await session.prompt_async(label)
        if text == S_CANCEL:
            raise KeyboardInterrupt
        if text.strip():
            return text


async def ask_menu(label: str | None = None) -> str:
    if label is None:
        label = tag("prompt", "> ")
    return await get_menu_session().prompt_async(label)


# ---------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------

def show_menu(chats: dict) -> list[tuple[str, dict]]:
    items = sorted(chats.items(),
                   key=lambda kv: kv[1].get("last_used", ""),
                   reverse=True)

    show_banner()
    subtitle = (
        tag("version", Color.Format.bold(get_version()))
        + "  "
        + tag("dim", f"[{get_theme_name()}]")
    )
    print("  " + subtitle)
    print("  " + tag("dim", "─" * 46))

    if not items:
        print("  " + tag("dim", "(no chats yet)"))
    else:
        for i, (cid, meta) in enumerate(items, 1):
            num = tag("chat_num", Color.Format.bold(f"{i:>2}."))
            chat_title = meta.get("title", "(untitled)")
            cid_short = tag("chat_id", f"[{cid[:8]}]")
            print(f"   {num}  {chat_title}  {cid_short}")

    print()
    new = tag("success", Color.Format.bold(" 0.")) + "  " + tag("success", "New chat")
    print(new)

    autosend = get_autosend()
    if autosend:
        preview = autosend.replace("\n", " ")
        if len(preview) > 40:
            preview = preview[:37] + "..."
        status = (
            tag("dim", " a  autosend: ")
            + tag("version", preview)
            + tag("dim", "   (e: edit, x: clear)")
        )
    else:
        status = tag("dim", " a  autosend: (none)   (e: edit)")
    print(" " + status)

    hints = (
        tag("dim", " r ")
        + tag("menu_action", "rename")
        + tag("dim", "   d ")
        + tag("menu_action", "delete")
        + tag("dim", "   x ")
        + tag("link", "export")
        + tag("dim", "   t ")
        + tag("menu_action", "theme")
        + tag("dim", "   v ")
        + tag("version", "version")
        + tag("dim", "   q ")
        + tag("menu_key", "quit")
    )
    print(" " + hints)
    print()
    return items


def _pick_chat(items, raw: str):
    if not raw.isdigit():
        return None
    idx = int(raw)
    if 1 <= idx <= len(items):
        return items[idx - 1]
    return None


async def menu(session, token) -> tuple[str, int | None, bool]:
    while True:
        stored = load_chats()
        chats = stored.get("chats", {})
        items = show_menu(chats)

        try:
            raw = await ask_menu()
        except EOFError:
            print()
            raise SystemExit(0)
        except KeyboardInterrupt:
            print()
            continue

        if raw == S_QUIT:
            raise SystemExit(0)
        if raw == S_CANCEL:
            continue

        # ---- Rename --------------------------------------------------
        if raw == S_RENAME:
            if not items:
                print(Color.MessagePresets.Warning("  Create a chat to rename it."))
                continue
            try:
                idx_raw = (await ask_menu("Which chat do you want to rename? ")).strip()
            except EOFError:
                raise SystemExit(0)
            except KeyboardInterrupt:
                print()
                continue
            if idx_raw == S_CANCEL or not idx_raw:
                continue
            picked = _pick_chat(items, idx_raw)
            if not picked:
                print(Color.MessagePresets.Error("  Invalid number."))
                continue
            cid, meta = picked
            try:
                new_title = (await ask_menu(
                    f"New title for '{meta.get('title', '(untitled)')}': "
                )).strip()
            except EOFError:
                raise SystemExit(0)
            except KeyboardInterrupt:
                print()
                continue
            if new_title and new_title != S_CANCEL:
                update_chat(cid, title=new_title)
                print(Color.MessagePresets.Success("  Renamed."))
            continue

        # ---- Delete --------------------------------------------------
        if raw == S_DELETE:
            if not items:
                print(Color.MessagePresets.Warning("  Create a chat to delete it."))
                continue
            try:
                idx_raw = (await ask_menu("Which chat do you want to delete? ")).strip()
            except EOFError:
                raise SystemExit(0)
            except KeyboardInterrupt:
                print()
                continue
            if idx_raw == S_CANCEL or not idx_raw:
                continue
            picked = _pick_chat(items, idx_raw)
            if not picked:
                print(Color.MessagePresets.Error("  Invalid number."))
                continue
            cid, meta = picked
            try:
                confirm = (await ask_menu(
                    f"Delete '{meta.get('title', '(untitled)')}'? [y/N]: "
                )).strip().lower()
            except EOFError:
                raise SystemExit(0)
            except KeyboardInterrupt:
                print()
                continue
            if confirm == "y":
                delete_chat(cid)
                print(Color.MessagePresets.Success("  Deleted."))
            continue

        # ---- Export --------------------------------------------------
        if raw == S_EXPORT:
            if not items:
                print(Color.MessagePresets.Warning("  Create a chat to export it."))
                continue
            try:
                idx_raw = (await ask_menu("Which chat do you want to export? ")).strip()
            except EOFError:
                raise SystemExit(0)
            except KeyboardInterrupt:
                print()
                continue
            if idx_raw == S_CANCEL or not idx_raw:
                continue
            picked = _pick_chat(items, idx_raw)
            if not picked:
                print(Color.MessagePresets.Error("  Invalid number."))
                continue
            cid, _ = picked
            path = export_chat_markdown(cid)
            if path:
                print(Color.MessagePresets.Success(f"  Exported to: {path}"))
            else:
                print(Color.MessagePresets.Warning("  No history to export for this chat."))
            continue

        # ---- Version -------------------------------------------------
        if raw == S_VERSION:
            try:
                current = get_version()
                print(Color.Format.dim(f"  Current version: {current}"))
                new_ver = (await ask_menu("New version (empty = keep): ")).strip()
            except EOFError:
                raise SystemExit(0)
            except KeyboardInterrupt:
                print()
                continue
            if new_ver and new_ver != S_CANCEL:
                set_version(new_ver)
                print(Color.MessagePresets.Success(f"  Version set to {new_ver}."))
            continue

        # ---- Theme ---------------------------------------------------
        if raw == S_THEME:
            themes = load_themes()
            names = list(themes.keys())
            print(tag("dim", "  Available themes:"))
            for i, name in enumerate(names, 1):
                marker = " *" if name == get_theme_name() else ""
                print(f"    {i}. {name}{marker}")
            try:
                choice = (await ask_menu("Pick theme: ")).strip()
            except EOFError:
                raise SystemExit(0)
            except KeyboardInterrupt:
                print()
                continue
            if choice == S_CANCEL or not choice:
                continue
            if choice.isdigit() and 1 <= int(choice) <= len(names):
                set_theme_name(names[int(choice) - 1])
                print(Color.MessagePresets.Success(f"  Theme set to {names[int(choice) - 1]}."))
            else:
                print(Color.MessagePresets.Error("  Invalid choice."))
            continue

        # ---- Autosend ------------------------------------------------
        if raw == S_AUTOSEND:
            try:
                print(Color.Format.dim(
                    "  Enter autosend message. Enter = submit, Ctrl+O = newline. Empty = clear."
                ))
                new_text = (await ask_menu("Autosend: ")).strip()
            except EOFError:
                raise SystemExit(0)
            except KeyboardInterrupt:
                print()
                continue
            if new_text == S_CANCEL:
                continue
            set_autosend(new_text)
            if new_text:
                print(Color.MessagePresets.Success("  Autosend set."))
            else:
                print(Color.MessagePresets.Success("  Autosend cleared."))
            continue

        # ---- New chat (0) --------------------------------------------
        if raw == "0":
            chat_id = await create_chat_session(session, token)
            print(Color.MessagePresets.Success(f"  Created new chat: {chat_id}"))
            return chat_id, None, True

        # ---- Resume by number ----------------------------------------
        if raw.isdigit() and 1 <= int(raw) <= len(items):
            cid, meta = items[int(raw) - 1]
            parent = meta.get("parent_message_id")
            print(Color.MessagePresets.Info(f"  Resuming: {cid}"))
            return cid, parent, False

        # ---- Resume by UUID ------------------------------------------
        try:
            uuid.UUID(raw)
            parent = chats.get(raw, {}).get("parent_message_id")
            return raw, parent, False
        except ValueError:
            print(Color.MessagePresets.Error("  Invalid input."))
            continue


# ---------------------------------------------------------------------
# Chat loop
# ---------------------------------------------------------------------

def _hyperlink(url: str, label: str) -> str:
    return f"\033]8;;{url}\033\\{label}\033]8;;\033\\"


async def chat_loop(session, token, chat_id: str, parent_message_id: int | None,
                    first_turn: bool):
    url = f"https://chat.deepseek.com/a/chat/s/{chat_id}"
    print(tag("dim", "  Chat: ") + tag("link", _hyperlink(url, url)))
    print(tag("dim", "  Enter: submit  |  Ctrl+O: newline"))
    print(tag("dim", "  Ctrl+C: back to menu  |  Ctrl+D or 'stop': quit"))

    if first_turn:
        autosend = get_autosend()
        if autosend:
            print()
            print(tag("dim", "  Autosending initial message..."))
            try:
                reply, response_id = await send_message(
                    session, token, autosend, chat_id, parent_message_id
                )
                print(tag("dim", "  Style acknowledged."))
                if response_id is not None:
                    parent_message_id = response_id
                update_chat(chat_id, parent_message_id=parent_message_id)

                fetched = await fetch_chat_title(session, token, chat_id)
                title = fetched or (autosend[:40] + ("..." if len(autosend) > 40 else ""))
                update_chat(chat_id, title=title)
                first_turn = False
            except (KeyboardInterrupt, asyncio.CancelledError):
                print(Color.MessagePresets.Warning("  (autosend interrupted)"))
            except Exception as e:
                print(Color.MessagePresets.Error(f"  Autosend error: {e}"))

    print()

    while True:
        try:
            prompt = await ask_multiline()
        except EOFError:
            print()
            raise SystemExit(0)
        except KeyboardInterrupt:
            print()
            return

        stripped = prompt.strip()
        low = stripped.lower()

        if low == "stop":
            raise SystemExit(0)
        if low in ("quit", "exit", "/quit", "/exit"):
            return
        if low == ":export":
            path = export_chat_markdown(chat_id)
            if path:
                print(Color.MessagePresets.Success(f"  Exported to: {path}"))
            else:
                print(Color.MessagePresets.Warning("  No history to export yet."))
            continue

        append_history(chat_id, "user", stripped)

        try:
            reply, response_id = await send_message(
                session, token, stripped, chat_id, parent_message_id
            )
        except (KeyboardInterrupt, asyncio.CancelledError):
            print()
            print(Color.MessagePresets.Warning("  (interrupted — back to menu)"))
            return
        except Exception as e:
            print()
            print(Color.MessagePresets.Error(f"  Error: {e}"))
            continue

        title_from_reply, reply = extract_title(reply)
        if title_from_reply:
            update_chat(chat_id, title=title_from_reply)

        append_history(chat_id, "assistant", reply)

        print()
        print(render_markdown(reply))
        print()

        if response_id is not None:
            parent_message_id = response_id

        update_chat(chat_id, parent_message_id=parent_message_id)

        if first_turn:
            fetched = await fetch_chat_title(session, token, chat_id)
            title = fetched or (stripped[:40] + ("..." if len(stripped) > 40 else ""))
            update_chat(chat_id, title=title)
            first_turn = False


# ---------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------

async def main():
    token = os.getenv("DEEPSEEK_TOKEN")
    if not token:
        raise ValueError("DEEPSEEK_TOKEN not set in .env")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                choice = await menu(session, token)
            except SystemExit:
                raise
            except (KeyboardInterrupt, asyncio.CancelledError):
                continue

            chat_id, parent, first_turn = choice
            try:
                await chat_loop(session, token, chat_id, parent, first_turn)
            except SystemExit:
                raise
            except (KeyboardInterrupt, asyncio.CancelledError):
                continue


if __name__ == "__main__":
    if "--test" in sys.argv:
        sample = (
            "# Heading 1\n"
            "## Heading 2\n\n"
            "Plain **bold** and *italic* and `code`.\n\n"
            "\\C:{cyan}cyan preset \U:onand underlined\U:off\n"
            "\\C:{red}red preset \\C:{yellow}then yellow\n"
            "\\Cx{FF5733}orange hex\n"
            "\\B:{blue}blue background\n"
            "\\Bx{330033}and a purple background\n"
            "~~strikethrough~~ and \\U:onunderlined text\U:off\n"
        )
        print(render_markdown(sample))
        sys.exit(0)

    try:
        asyncio.run(main())
    except SystemExit:
        pass
    except (KeyboardInterrupt, EOFError):
        pass