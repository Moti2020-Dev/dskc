import asyncio
import uuid
import aiohttp
from lib_color import Color
from . import config
from .api import create_chat_session
from .chat import chat_loop
from .export import export_chat_markdown
from .sessions import (
    ask_menu, ask_input,
    S_QUIT, S_CANCEL, S_RENAME, S_DELETE, S_EXPORT, S_VERSION, S_THEME, S_AUTOSEND,
)
from .storage import load_chats, update_chat, delete_chat
from .themes import tag
from .banner import show_banner

from .debug import is_debug

def show_menu(chats: dict):
    items = sorted(chats.items(),
                   key=lambda kv: kv[1].get("last_used", ""),
                   reverse=True)

    show_banner()

    subtitle = (
        tag("version", Color.Format.bold(config.get_version()))
        + "  "
        + tag("dim", f"[{config.get_theme_name()}]")
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
    print(tag("success", Color.Format.bold(" 0.")) + "  " + tag("success", "New chat"))

    autosend = config.get_autosend()
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
        tag("dim", " r ") + tag("menu_action", "rename")
        + tag("dim", "   d ") + tag("menu_action", "delete")
        + tag("dim", "   x ") + tag("link", "export")
        + tag("dim", "   t ") + tag("menu_action", "theme")
        + tag("dim", "   v ") + tag("version", "version")
        + tag("dim", "   q ") + tag("menu_key", "quit")
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


async def menu(session, token):
    while True:
        items = show_menu(load_chats().get("chats", {}))

        try:
            raw = await ask_menu()
        except EOFError:
            print()
            raise SystemExit(0)
        except KeyboardInterrupt:
            print()
            continue

        if is_debug():
            print(f"[DEBUG] raw = {raw!r}")
            print(f"[DEBUG] items len = {len(items)}")

        if raw == S_QUIT:
            raise SystemExit(0)
        if raw == S_CANCEL:
            continue

        if raw == S_RENAME:
            if not items:
                print(Color.MessagePresets.Warning("  Create a chat to rename it."))
                continue
            idx_raw = await _ask_idx("Which chat do you want to rename? ")
            if idx_raw is None:
                continue
            picked = _pick_chat(items, idx_raw)
            if not picked:
                print(Color.MessagePresets.Error("  Invalid number."))
                continue
            cid, meta = picked
            try:
                new_title = (await ask_input(
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

        if raw == S_DELETE:
            if not items:
                print(Color.MessagePresets.Warning("  Create a chat to delete it."))
                continue
            idx_raw = await _ask_idx("Which chat do you want to delete? ")
            if idx_raw is None:
                continue
            picked = _pick_chat(items, idx_raw)
            if not picked:
                print(Color.MessagePresets.Error("  Invalid number."))
                continue
            cid, meta = picked
            try:
                confirm = (await ask_input(
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

        if raw == S_EXPORT:
            if not items:
                print(Color.MessagePresets.Warning("  Create a chat to export it."))
                continue
            idx_raw = await _ask_idx("Which chat do you want to export? ")
            if idx_raw is None:
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

        if raw == S_VERSION:
            try:
                current = config.get_version()
                print(Color.Format.dim(f"  Current version: {current}"))
                new_ver = (await ask_input("New version (empty = keep): ")).strip()
            except EOFError:
                raise SystemExit(0)
            except KeyboardInterrupt:
                print()
                continue
            if new_ver and new_ver != S_CANCEL:
                config.set_version(new_ver)
                print(Color.MessagePresets.Success(f"  Version set to {new_ver}."))
            continue

        if raw == S_THEME:
            themes = config.load_themes()
            names = list(themes.keys())
            print(tag("dim", "  Available themes:"))
            for i, name in enumerate(names, 1):
                marker = " *" if name == config.get_theme_name() else ""
                print(f"    {i}. {name}{marker}")
            try:
                choice = (await ask_input("Pick theme: ")).strip()
            except EOFError:
                raise SystemExit(0)
            except KeyboardInterrupt:
                print()
                continue
            if choice == S_CANCEL or not choice:
                continue
            if choice.isdigit() and 1 <= int(choice) <= len(names):
                config.set_theme_name(names[int(choice) - 1])
                print(Color.MessagePresets.Success(f"  Theme set to {names[int(choice) - 1]}."))
            else:
                print(Color.MessagePresets.Error("  Invalid choice."))
            continue

        if raw == S_AUTOSEND:
            try:
                print(Color.Format.dim(
                    "  Enter autosend message. Enter = submit, Ctrl+O = newline. Empty = clear."
                ))
                new_text = (await ask_input("Autosend: ")).strip()
            except EOFError:
                raise SystemExit(0)
            except KeyboardInterrupt:
                print()
                continue
            if new_text == S_CANCEL:
                continue
            config.set_autosend(new_text)
            if new_text:
                print(Color.MessagePresets.Success("  Autosend set."))
            else:
                print(Color.MessagePresets.Success("  Autosend cleared."))
            continue

        if raw == "0":
            chat_id = await create_chat_session(session, token)
            print(Color.MessagePresets.Success(f"  Created new chat: {chat_id}"))
            return chat_id, None, True

        if raw.isdigit() and 1 <= int(raw) <= len(items):
            cid, meta = items[int(raw) - 1]
            parent = meta.get("parent_message_id")
            if is_debug():
                print(f"[DEBUG] resuming cid={cid} parent={parent}")
                print(Color.MessagePresets.Info(f"  Resuming: {cid}"))
            return cid, parent, False

        try:
            uuid.UUID(raw)
            parent = load_chats().get("chats", {}).get(raw, {}).get("parent_message_id")
            return raw, parent, False
        except ValueError:
            print(Color.MessagePresets.Error("  Invalid input."))
            continue


async def _ask_idx(question: str) -> str | None:
    """Ask for a chat number. Returns the raw string, or None if cancelled."""
    try:
        idx_raw = (await ask_input(question)).strip()
    except EOFError:
        raise SystemExit(0)
    except KeyboardInterrupt:
        print()
        return None
    if idx_raw == S_CANCEL or not idx_raw:
        return None
    return idx_raw


async def run(token: str):
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