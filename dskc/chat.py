import asyncio
import re

from lib_color import Color

from . import config, reference
from .api import fetch_chat_title, send_message
from .colors import render_markdown
from .copy import ContainerStore, handle_copy
from .debug import dbg
from .export import export_chat_markdown, handle_save
from .load import read_load_file
from .notify import notify
from .sessions import S_CANCEL, ask_input, ask_multiline
from .storage import (
    append_history,
    load_chats,
    load_history,
    truncate_history_tail,
    update_chat,
)
from .terminal import reset_title, set_title
from .themes import tag

_TITLE_RE = re.compile(r"^\\\{([^}]*)\}\\\s*\n?", re.MULTILINE)


def _hyperlink(url: str, label: str) -> str:
    return f"\033]8;;{url}\033\\{label}\033]8;;\033\\"


def _extract_title(text: str):
    m = _TITLE_RE.match(text)
    if m:
        return m.group(1).strip(), text[m.end():]
    return None, text


def _chat_render_fn(chat_id: str):
    data = load_history(chat_id)
    if data is None:
        return None
    parts = []
    for msg in data.get("messages", []):
        role = "You" if msg.get("role") == "user" else "DeepSeek"
        parts.append(f"### {role}\n\n{msg.get('content', '')}")
    return "\n\n".join(parts)


async def _send_and_render(session, token, chat_id, parent_message_id,
                           prompt: str, store: ContainerStore,
                           *, truncate_before: bool = False):
    if truncate_before:
        truncate_history_tail(chat_id, 2)

    append_history(chat_id, "user", prompt)

    try:
        reply, response_id = await send_message(
            session, token, prompt, chat_id, parent_message_id
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        print()
        print(Color.MessagePresets.Warning("  (interrupted)"))
        return parent_message_id, prompt, None
    except Exception as e:  # noqa: BLE001
        print()
        print(Color.MessagePresets.Error(f"  Error: {e}"))
        return parent_message_id, prompt, None

    title_from_reply, reply = _extract_title(reply)
    if title_from_reply:
        dbg("title from reply", title_from_reply)
        update_chat(chat_id, title=title_from_reply)
        set_title(f"DSKC — {title_from_reply}")

    append_history(chat_id, "assistant", reply)

    store.clear()
    print()
    print(render_markdown(reply, store=store))
    print()

    new_parent = response_id if response_id is not None else parent_message_id
    update_chat(chat_id, parent_message_id=new_parent)
    return new_parent, prompt, reply


async def chat_loop(session, token, chat_id: str, parent_message_id,
                    first_turn: bool):
    url = f"https://chat.deepseek.com/a/chat/s/{chat_id}"
    title = load_chats().get("chats", {}).get(chat_id, {}).get("title", "(untitled)")
    set_title(f"DSKC — {title}")

    print(
        tag("dim", "  Chat: ")
        + tag("info", title)
        + tag("dim", " — ")
        + tag("link", _hyperlink(url, url))
    )
    print(tag("dim", "  Enter: submit  |  Ctrl+O: newline"))
    print(tag("dim", "  Ctrl+C: back to menu  |  Ctrl+D or 'stop': quit"))
    print(tag("dim", "  :help for commands"))

    store = ContainerStore()
    last_user_message: str | None = None
    last_parent_id = parent_message_id
    last_reply: str | None = None

    # Draft restore
    draft = config.get_draft(chat_id)
    if draft:
        print(tag("dim", "  (restored unsent draft)"))
        try:
            edited = (await ask_input("Draft: ")).strip()
        except EOFError:
            reset_title()
            raise SystemExit(0)
        except KeyboardInterrupt:
            print()
            edited = ""
        if edited:
            draft = edited
        else:
            draft = ""
        config.clear_draft(chat_id)

    if first_turn:
        autosend = config.get_autosend()
        if autosend:
            print()
            print(tag("dim", "  Autosending initial message..."))
            try:
                _, response_id = await send_message(
                    session, token, autosend, chat_id, parent_message_id
                )
                print(tag("dim", "  Style acknowledged."))
                if response_id is not None:
                    parent_message_id = response_id
                update_chat(chat_id, parent_message_id=parent_message_id)

                fetched = await fetch_chat_title(session, token, chat_id)
                t = fetched or (autosend[:40] + ("..." if len(autosend) > 40 else ""))
                update_chat(chat_id, title=t)
                set_title(f"DSKC — {t}")
                first_turn = False
            except (KeyboardInterrupt, asyncio.CancelledError):
                print(Color.MessagePresets.Warning("  (autosend interrupted)"))
            except Exception as e:  # noqa: BLE001
                print(Color.MessagePresets.Error(f"  Autosend error: {e}"))

    print()

    while True:
        try:
            if draft:
                prompt = draft
                draft = ""
            else:
                prompt = await ask_multiline()
        except EOFError:
            print()
            reset_title()
            raise SystemExit(0)
        except KeyboardInterrupt:
            print()
            reset_title()
            return

        stripped = prompt.strip()
        low = stripped.lower()

        if low == "stop":
            reset_title()
            raise SystemExit(0)
        if low in ("quit", "exit", "/quit", "/exit"):
            reset_title()
            return

        # Colon commands. Keep original case for file paths.
        if low.startswith(":"):
            cmd, _, _ = stripped[1:].partition(" ")
            args_orig = stripped[1 + len(cmd):].lstrip()

            if cmd == "export":
                path = export_chat_markdown(chat_id)
                if path:
                    print(Color.MessagePresets.Success(f"  Exported to: {path}"))
                else:
                    print(Color.MessagePresets.Warning("  No history to export yet."))
                continue

            if cmd == "save":
                handle_save(args_orig, chat_id)
                continue

            if cmd == "load":
                text = read_load_file(args_orig)
                if text is None:
                    continue
                # Send the loaded text as a normal message
                stripped = text
                last_user_message = stripped
                last_parent_id = parent_message_id
                new_parent, _, last_reply = await _send_and_render(
                    session, token, chat_id, parent_message_id, stripped, store
                )
                parent_message_id = new_parent
                notify("DSKC", "Reply received")
                if first_turn:
                    fetched = await fetch_chat_title(session, token, chat_id)
                    title = fetched or (stripped[:40] + ("..." if len(stripped) > 40 else ""))
                    update_chat(chat_id, title=title)
                    set_title(f"DSKC — {title}")
                    first_turn = False
                continue

            if cmd == "copy":
                rendered = render_markdown(last_reply) if last_reply else None
                handle_copy(
                    args_orig, store,
                    last_reply_raw=last_reply,
                    last_reply_rendered=rendered,
                    chat_render_fn=lambda: _chat_render_fn(chat_id),
                )
                continue

            if cmd == "retry":
                if last_user_message is None:
                    print(Color.MessagePresets.Warning("  Nothing to retry yet."))
                    continue
                new_parent, _, last_reply = await _send_and_render(
                    session, token, chat_id, last_parent_id,
                    last_user_message, store, truncate_before=True,
                )
                parent_message_id = new_parent
                notify("DSKC", "Reply received")
                continue

            if cmd == "edit":
                if last_user_message is None:
                    print(Color.MessagePresets.Warning("  Nothing to edit yet."))
                    continue
                try:
                    new_text = (await ask_input(
                        f"Edit (was: '{last_user_message[:50]}'): "
                    )).strip()
                except EOFError:
                    reset_title()
                    raise SystemExit(0)
                except KeyboardInterrupt:
                    print()
                    continue
                if not new_text or new_text == S_CANCEL:
                    continue
                last_user_message = new_text
                new_parent, _, last_reply = await _send_and_render(
                    session, token, chat_id, last_parent_id,
                    new_text, store, truncate_before=True,
                )
                parent_message_id = new_parent
                notify("DSKC", "Reply received")
                continue

            if cmd == "undo":
                truncate_history_tail(chat_id, 2)
                print(Color.MessagePresets.Success("  Last exchange removed from local history."))
                continue

            if reference.dispatch(cmd, args_orig):
                continue

            print(Color.MessagePresets.Error(f"  Unknown command: :{cmd}"))
            continue

        dbg("user message", (len(stripped), stripped[:60]))
        last_user_message = stripped
        last_parent_id = parent_message_id

        new_parent, _, last_reply = await _send_and_render(
            session, token, chat_id, parent_message_id, stripped, store
        )
        parent_message_id = new_parent
        notify("DSKC", "Reply received")

        if first_turn:
            fetched = await fetch_chat_title(session, token, chat_id)
            title = fetched or (stripped[:40] + ("..." if len(stripped) > 40 else ""))
            update_chat(chat_id, title=title)
            set_title(f"DSKC — {title}")
            first_turn = False