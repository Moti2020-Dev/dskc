"""
Copy Containers + clipboard helpers.

The model emits blocks like:

    copy:BlockName
    ... content ...
    endcopy

The parser stashes the content under the block name and replaces it in the
rendered output with a dim marker. The user can then type /copy BlockName
to place the content on the clipboard.

Clipboard uses OSC 52 which most modern terminals support. Falls back to
printing the content to stdout when the user disables OSC 52 or the terminal
does not understand it.
"""

import base64
import re
import sys

from . import config
from .debug import dbg


# ---------------------------------------------------------------------
# Container parsing
# ---------------------------------------------------------------------

_CONTAINER_RE = re.compile(
    r"^copy:([A-Za-z_][A-Za-z0-9_]*)[ \t]*\n(.*?)\nendcopy[ \t]*$",
    re.MULTILINE | re.DOTALL,
)


class ContainerStore:
    """Per-reply store of copy containers."""

    def __init__(self):
        self.blocks: dict[str, str] = {}

    def clear(self):
        self.blocks.clear()

    def add(self, name: str, content: str):
        self.blocks[name] = content
        dbg("container added", (name, len(content)))

    def get(self, name: str) -> str | None:
        return self.blocks.get(name)

    def names(self) -> list[str]:
        return list(self.blocks.keys())


def extract_containers(text: str, store: ContainerStore) -> str:
    """
    Find copy:NAME ... endcopy blocks, stash them in the store, replace
    each with a dim marker in the visible text.
    """
    def _stash(m):
        name = m.group(1)
        content = m.group(2)
        store.add(name, content)
        marker = f"\033[2m[Block: {name}]\033[22m"
        return marker

    return _CONTAINER_RE.sub(_stash, text)


# ---------------------------------------------------------------------
# Clipboard emission
# ---------------------------------------------------------------------

def _osc52(payload: str) -> bool:
    """Emit an OSC 52 sequence to copy payload to the system clipboard."""
    try:
        b64 = base64.b64encode(payload.encode("utf-8")).decode("ascii")
        # OSC 52 ; c ; <base64> ST
        sys.stdout.write(f"\033]52;c;{b64}\007")
        sys.stdout.flush()
        return True
    except Exception as e:  # noqa: BLE001
        dbg("osc52 failed", str(e))
        return False


def copy_to_clipboard(text: str) -> bool:
    """
    Copy text to the system clipboard. Respects the config preference.
    Returns True if something was sent to the terminal.
    """
    mode = config.get_clipboard()
    if mode == "stdout":
        print(text)
        return True
    # auto or osc52
    ok = _osc52(text)
    if not ok:
        print(text)
    return ok


# ---------------------------------------------------------------------
# Command handling
# ---------------------------------------------------------------------

def parse_args(args: str) -> tuple[dict, list[str]]:
    """
    Split arguments into flags and positional names.
    Supports --rendered and --chat.
    """
    flags = {"rendered": False, "chat": False}
    names = []
    for token in args.split():
        if token == "--rendered":
            flags["rendered"] = True
        elif token == "--chat":
            flags["chat"] = True
        else:
            names.append(token)
    return flags, names


def handle_copy(args: str, store: ContainerStore, chat_id: str | None,
                render_fn) -> bool:
    """
    Handle /copy from the chat prompt. Returns True if handled.
    render_fn: callable that takes a chat_id and returns (raw_markdown, rendered)
    """
    flags, names = parse_args(args)

    if flags["chat"]:
        if chat_id is None:
            print("  No chat to export.")
            return True
        result = render_fn(chat_id)
        if result is None:
            print("  No history to copy.")
            return True
        raw, rendered = result
        payload = rendered if flags["rendered"] else raw
        copy_to_clipboard(payload)
        print(f"  Copied chat as {'rendered' if flags['rendered'] else 'markdown'}.")
        return True

    if not names:
        if not store.names():
            print("  No blocks available. Ask the model to emit copy:NAME...endcopy.")
            return True
        print("  Available blocks:")
        for name in store.names():
            print(f"    {name}")
        return True

    name = names[0]
    content = store.get(name)
    if content is None:
        print(f"  No block named '{name}'.")
        return True

    copy_to_clipboard(content)
    print(f"  Copied '{name}' ({len(content)} chars).")
    return True