import asyncio
import re
from lib_color import Color
from . import config
from .api import send_message, fetch_chat_title
from .colors import render_markdown
from .debug import dbg
from .export import export_chat_markdown
from .sessions import ask_multiline
from .storage import update_chat, append_history, load_chats
from .themes import tag


_TITLE_RE = re.compile(r"^\\\{([^}]*)\}\\\s*\n?", re.MULTILINE)


def _hyperlink(url: str, label: str) -> str:
    return f"\033]8;;{url}\033\\{label}\033]8;;\033\\"


def _extract_title(text: str):
    m = _TITLE_RE.match(text)
    if m:
        return m.group(1).strip(), text[m.end():]
    return None, text


async def chat_loop(session, token, chat_id: str, parent_message_id,
                    first_turn: bool):
    url = f"https://chat.deepseek.com/a/chat/s/{chat_id}"
    title = load_chats().get("chats", {}).get(chat_id, {}).get("title", "(untitled)")
    print(
        tag("dim", "  Chat: ")
        + tag("info", title)
        + tag("dim", " — ")
        + tag("link", _hyperlink(url, url))
    )
    print(tag("dim", "  Enter: submit  |  Ctrl+O: newline"))
    print(tag("dim", "  Ctrl+C: back to menu  |  Ctrl+D or 'stop': quit"))

    if first_turn:
        autosend = config.get_autosend()
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

        dbg("user message", (len(stripped), stripped[:60]))
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

        title_from_reply, reply = _extract_title(reply)
        if title_from_reply:
            dbg("title from reply", title_from_reply)
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