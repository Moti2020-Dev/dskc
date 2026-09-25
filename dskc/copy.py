import base64
import re
import sys

from lib_color import Color, strip_ansi

from . import config
from .debug import dbg

_CONTAINER_RE = re.compile(
    r"^copy:([A-Za-z_][A-Za-z0-9_]*)[ \t]*\n(.*?)\nendcopy[ \t]*$",
    re.MULTILINE | re.DOTALL,
)


class ContainerStore:
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
    def _stash(m):
        name = m.group(1)
        content = m.group(2)
        store.add(name, content)
        return f"\033[2m[Block: {name}]\033[22m"

    return _CONTAINER_RE.sub(_stash, text)


def _osc52(payload: str) -> bool:
    try:
        b64 = base64.b64encode(payload.encode("utf-8")).decode("ascii")
        sys.stdout.write(f"\033]52;c;{b64}\007")
        sys.stdout.flush()
        return True
    except Exception as e:  # noqa: BLE001
        dbg("osc52 failed", str(e))
        return False


def copy_to_clipboard(text: str) -> bool:
    mode = config.get_clipboard()
    if mode == "stdout":
        print(text)
        return True
    ok = _osc52(text)
    if not ok:
        print(text)
    return ok


def _parse_args(args: str) -> tuple[set[str], list[str]]:
    flags: set[str] = set()
    names: list[str] = []
    for token in args.split():
        if token.startswith("--"):
            flags.add(token)
        else:
            names.append(token)
    return flags, names


def handle_copy(args: str, store: ContainerStore,
                last_reply_raw: str | None,
                last_reply_rendered: str | None,
                chat_render_fn) -> bool:
    flags, names = _parse_args(args)

    if "--chat" in flags:
        result = chat_render_fn()
        if result is None:
            print(Color.MessagePresets.Warning("  No history to copy."))
            return True
        payload = result
        if "--plain" in flags or "--rendered" not in flags:
            payload = strip_ansi(payload)
        copy_to_clipboard(payload)
        print(Color.MessagePresets.Success(
            f"  Copied chat ({len(payload)} chars)."
        ))
        return True

    if "--last" in flags:
        if last_reply_raw is None:
            print(Color.MessagePresets.Warning("  No reply to copy yet."))
            return True
        if "--rendered" in flags and last_reply_rendered is not None:
            payload = last_reply_rendered
        else:
            payload = last_reply_raw
        if "--plain" in flags:
            payload = strip_ansi(payload)
        copy_to_clipboard(payload)
        print(Color.MessagePresets.Success(
            f"  Copied last reply ({len(payload)} chars)."
        ))
        return True

    if names:
        name = names[0]
        content = store.get(name)
        if content is None:
            print(Color.MessagePresets.Error(f"  No block named '{name}'."))
            return True
        if "--plain" in flags:
            content = strip_ansi(content)
        copy_to_clipboard(content)
        print(Color.MessagePresets.Success(
            f"  Copied '{name}' ({len(content)} chars)."
        ))
        return True

    if not store.names():
        print(Color.MessagePresets.Warning(
            "  No blocks. Use --last, --chat, or ask the model to emit copy:NAME...endcopy."
        ))
        return True
    print(Color.Format.dim("  Available blocks:"))
    for name in store.names():
        print(f"    {name}")
    return True