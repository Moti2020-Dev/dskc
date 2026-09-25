import datetime
import pathlib

from lib_color import Color, strip_ansi

from .colors import render_markdown
from .debug import dbg
from .paths import PROJECT_ROOT
from .storage import load_chats, load_history


def export_chat_markdown(chat_id: str):
    data = load_history(chat_id)
    if data is None:
        dbg("export: no history", chat_id[:8])
        return None
    title = load_chats().get("chats", {}).get(chat_id, {}).get("title", chat_id)
    out_path = PROJECT_ROOT / f"export_{chat_id[:8]}.md"

    lines = [
        f"# {title}",
        "",
        f"- Chat ID: `{chat_id}`",
        f"- URL: https://chat.deepseek.com/a/chat/s/{chat_id}",
        f"- Exported: {datetime.datetime.now(datetime.UTC).isoformat()}",
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
    dbg("export written", str(out_path))
    return out_path


def chat_as_markdown(chat_id: str) -> str | None:
    data = load_history(chat_id)
    if data is None:
        return None
    parts = []
    for msg in data.get("messages", []):
        role = "You" if msg.get("role") == "user" else "DeepSeek"
        parts.append(f"### {role}\n\n{msg.get('content', '')}")
    return "\n\n".join(parts)


def last_reply_text(chat_id: str, rendered: bool = False) -> str | None:
    data = load_history(chat_id)
    if data is None:
        return None
    for msg in reversed(data.get("messages", [])):
        if msg.get("role") == "assistant":
            text = msg.get("content", "")
            if rendered:
                return render_markdown(text)
            return text
    return None


def _parse_save_args(args: str) -> tuple[set[str], str | None]:
    flags: set[str] = set()
    words: list[str] = []
    for token in args.split():
        if token.startswith("--"):
            flags.add(token)
        else:
            words.append(token)
    name = " ".join(words) if words else None
    return flags, name


def _default_save_name(chat_id: str) -> str:
    ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d-%H%M%S")
    return f"reply_{chat_id[:8]}_{ts}.md"


def handle_save(args: str, chat_id: str) -> bool:
    flags, name = _parse_save_args(args)

    if name is None:
        name = _default_save_name(chat_id)
    path = pathlib.Path(name).expanduser()

    if "--chat" in flags:
        text = chat_as_markdown(chat_id)
        if text is None:
            print(Color.MessagePresets.Warning("  No history to save."))
            return True
    else:
        text = last_reply_text(chat_id, rendered=("--rendered" in flags))
        if text is None:
            print(Color.MessagePresets.Warning("  No reply to save yet."))
            return True

    if "--no-ansi" in flags:
        text = strip_ansi(text)

    mode = "a" if "--append" in flags else "w"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open(mode, encoding="utf-8") as f:
            f.write(text)
    except OSError as e:
        print(Color.MessagePresets.Error(f"  Save failed: {e}"))
        return True

    verb = "Appended" if mode == "a" else "Saved"
    print(Color.MessagePresets.Success(
        f"  {verb} {len(text)} chars to {path.resolve()}"
    ))
    dbg("save wrote", (str(path), mode, len(text)))
    return True