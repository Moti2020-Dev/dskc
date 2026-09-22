import asyncio
import os
import json
import uuid
import sys
import base64
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

DEBUG = "--debug" in sys.argv
CHATS_FILE = pathlib.Path.home() / ".deepseek_chats.json"


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
# Custom color escapes (run before Markdown.render)
# ---------------------------------------------------------------------
#
#   \0xRRGGBB{text}   foreground from hex
#   \C:name{text}     foreground preset
#   \B:name{text}     background preset
#
# Implemented with a hand-written scanner so nothing can leak.
# ---------------------------------------------------------------------

def _apply_custom(text: str) -> str:
    result = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "\\" and i + 1 < n:
            # \0xRRGGBB{...}
            if text.startswith("\\0x", i):
                j = i + 3
                hex_start = j
                while j < n and j - hex_start < 6 and text[j] in "0123456789abcdefABCDEF":
                    j += 1
                if j - hex_start == 6 and j < n and text[j] == "{":
                    k = text.find("}", j + 1)
                    if k != -1:
                        value = int(text[hex_start:j], 16)
                        r = (value >> 16) & 0xFF
                        g = (value >> 8) & 0xFF
                        b = value & 0xFF
                        body = text[j + 1:k]
                        result.append(Color.Basic.fg(r, g, b) + body + RESET)
                        i = k + 1
                        continue
            # \C:name{...}
            if text.startswith("\\C:", i):
                j = i + 3
                name_start = j
                while j < n and (text[j].isalnum() or text[j] == "_"):
                    j += 1
                if j > name_start and j < n and text[j] == "{":
                    k = text.find("}", j + 1)
                    if k != -1:
                        name = text[name_start:j]
                        body = text[j + 1:k]
                        fn = getattr(Color.ColorPresets, name, None)
                        result.append(fn(body) if fn else body)
                        i = k + 1
                        continue
            # \B:name{...}
            if text.startswith("\\B:", i):
                j = i + 3
                name_start = j
                while j < n and (text[j].isalnum() or text[j] == "_"):
                    j += 1
                if j > name_start and j < n and text[j] == "{":
                    k = text.find("}", j + 1)
                    if k != -1:
                        name = text[name_start:j]
                        body = text[j + 1:k]
                        fn = getattr(Color.ColorPresets, name, None)
                        if fn:
                            sentinel = "\x00"
                            wrapped = fn(sentinel)
                            prefix = wrapped.split(sentinel)[0].replace("[38;2;", "[48;2;").replace("[38;5;", "[48;5;")
                            result.append(f"{prefix}{body}{RESET}")
                        else:
                            result.append(body)
                        i = k + 1
                        continue
        result.append(text[i])
        i += 1
    return "".join(result)


def render_markdown(text: str) -> str:
    return Markdown.render(_apply_custom(text))


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
# Prompt sessions
# ---------------------------------------------------------------------

def build_chat_session() -> PromptSession:
    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        event.current_buffer.validate_and_handle()

    @kb.add("s-enter")
    def _(event):
        event.current_buffer.insert_text("\n")

    @kb.add("escape", "enter")
    def _(event):
        event.current_buffer.insert_text("\n")

    return PromptSession(
        key_bindings=kb,
        multiline=True,
        prompt_continuation=lambda width, line_number, is_soft_wrap: "  | ",
        editing_mode=EditingMode.EMACS,
    )


def build_menu_session() -> PromptSession:
    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        event.current_buffer.validate_and_handle()

    return PromptSession(key_bindings=kb, editing_mode=EditingMode.EMACS)


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


def ask_multiline(label: str = "Prompt: ") -> str:
    session = get_chat_session()
    while True:
        text = session.prompt(label)
        if text.strip():
            return text


def ask_menu(label: str = "Select: ") -> str:
    return get_menu_session().prompt(label)


# ---------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------

def show_menu(chats: dict) -> list[tuple[str, dict]]:
    items = sorted(chats.items(),
                   key=lambda kv: kv[1].get("last_used", ""),
                   reverse=True)

    banner = f"{Color.Basic.fg(100, 200, 255)}{Color.Format.bold('◆  DeepSeek Terminal')}{RESET}"
    print()
    print("  " + banner)
    print("  " + Color.Format.dim("─" * 46))

    if not items:
        print("  " + Color.Format.dim("(no chats yet)"))
    else:
        palette = [
            (255, 215, 0), (0, 220, 220), (170, 220, 255), (200, 180, 255),
            (180, 255, 180), (255, 200, 150), (255, 170, 220), (200, 200, 200),
        ]
        for i, (cid, meta) in enumerate(items, 1):
            r, g, b = palette[(i - 1) % len(palette)]
            num = f"{Color.Basic.fg(r, g, b)}{Color.Format.bold(f'{i:>2}.')}{RESET}"
            title = meta.get("title", "(untitled)")
            cid_short = f"{Color.Basic.fg(110, 110, 110)}[{cid[:8]}]{RESET}"
            print(f"   {num}  {title}  {cid_short}")

    print()
    new = f"{Color.Basic.fg(0, 220, 120)}{Color.Format.bold(' 0.')}{RESET}  {Color.Basic.fg(0, 220, 120)}New chat{RESET}"
    print(new)

    hints = (
        Color.Format.dim(" r <n> ")
        + Color.Basic.fg(200, 180, 255) + "rename" + RESET
        + Color.Format.dim("   d <n> ")
        + Color.Basic.fg(255, 130, 130) + "delete" + RESET
        + Color.Format.dim("   q ")
        + Color.Basic.fg(180, 180, 180) + "quit" + RESET
    )
    print(" " + hints)
    print()
    return items


async def menu(session, token) -> tuple[str, int | None, bool]:
    while True:
        stored = load_chats()
        chats = stored.get("chats", {})
        items = show_menu(chats)

        try:
            raw = ask_menu()
        except EOFError:
            print()
            raise SystemExit(0)
        except KeyboardInterrupt:
            print()
            continue

        raw = raw.strip()
        low = raw.lower()

        if low in ("q", "quit", "exit", "stop"):
            raise SystemExit(0)

        if low.startswith("r "):
            try:
                idx = int(low.split()[1])
                cid, meta = items[idx - 1]
            except (ValueError, IndexError):
                print(Color.MessagePresets.Error("  Invalid number."))
                continue
            try:
                new_title = ask_menu(
                    f"New title for '{meta.get('title', '(untitled)')}': "
                ).strip()
            except EOFError:
                raise SystemExit(0)
            except KeyboardInterrupt:
                print()
                continue
            if new_title:
                update_chat(cid, title=new_title)
                print(Color.MessagePresets.Success("  Renamed."))
            continue

        if low.startswith("d "):
            try:
                idx = int(low.split()[1])
                cid, meta = items[idx - 1]
            except (ValueError, IndexError):
                print(Color.MessagePresets.Error("  Invalid number."))
                continue
            try:
                confirm = ask_menu(
                    f"Delete '{meta.get('title', '(untitled)')}'? [y/N]: "
                ).strip().lower()
            except EOFError:
                raise SystemExit(0)
            except KeyboardInterrupt:
                print()
                continue
            if confirm == "y":
                delete_chat(cid)
                print(Color.MessagePresets.Success("  Deleted."))
            continue

        if raw == "0":
            chat_id = await create_chat_session(session, token)
            print(Color.MessagePresets.Success(f"  Created new chat: {chat_id}"))
            return chat_id, None, True

        if raw.isdigit() and 1 <= int(raw) <= len(items):
            cid, meta = items[int(raw) - 1]
            parent = meta.get("parent_message_id")
            print(Color.MessagePresets.Info(f"  Resuming: {cid}"))
            return cid, parent, False

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

async def chat_loop(session, token, chat_id: str, parent_message_id: int | None,
                    first_turn: bool):
    print(Color.Format.dim("  Enter: submit  |  Shift+Enter / Alt+Enter: newline"))
    print(Color.Format.dim("  Ctrl+C: back to menu  |  Ctrl+D or 'stop': quit"))
    print()

    while True:
        try:
            prompt = await asyncio.to_thread(ask_multiline)
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
            "- bullet one\n"
            "- bullet two\n\n"
            "> a quote\n\n"
            "A [link](https://example.com).\n\n"
            "Custom: \\0xFF5733{orange} and \\C:cyan{cyan} and \\B:yellow{bg}.\n\n"
            "```python\nprint('hello')\n```\n\n"
            "---\n"
        )
        print(render_markdown(sample))
        sys.exit(0)

    try:
        asyncio.run(main())
    except SystemExit:
        pass
    except (KeyboardInterrupt, EOFError):
        pass