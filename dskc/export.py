import datetime
from .paths import PROJECT_ROOT
from .storage import load_chats, load_history
from .debug import dbg


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
    dbg("export written", str(out_path))
    return out_path