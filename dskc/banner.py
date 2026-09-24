import re
from lib_color import Color, RESET
from .themes import tag

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

BANNER_INNER = 42
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m|\x1b\]8;;[^\x1b]*\x1b\\\\")


def _gradient_text(text: str) -> str:
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
        pos = visible.index(i)
        t = pos / max(1, len(visible) - 1)
        idx = int(round(t * (n - 1)))
        r, g, b = stops[idx]
        out.append(f"{Color.Basic.fg(r, g, b)}{ch}")
    out.append(RESET)
    return "".join(out)


def _banner_line(content: str) -> str:
    visible = _ANSI_RE.sub("", content)
    vis_len = len(visible)
    if vis_len > BANNER_INNER:
        content = content[:BANNER_INNER]
        vis_len = BANNER_INNER
    pad = BANNER_INNER - vis_len
    return content + (" " * pad)


def show_banner():
    border = tag("dim", "▌")
    top = tag("dim", "▛" + "▀" * (BANNER_INNER + 1))
    bottom = tag("dim", "▙" + "▄" * (BANNER_INNER + 1))

    line1 = _gradient_text(_banner_line("  ◆  D S K C  ·  D E E P S E E K"))
    line2 = _gradient_text(_banner_line("     a command-line client"))

    print()
    print(" " + top)
    print(" " + border + line1 + tag("dim", "▐"))
    print(" " + border + line2 + tag("dim", "▐"))
    print(" " + bottom)