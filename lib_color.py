"""
Terminal color library with true 24-bit RGB + a markdown renderer.

No external dependencies.
"""

import os
import re


# ---------------------------------------------------------------------
# Color capability detection
# ---------------------------------------------------------------------

def _detect_mode() -> str:
    ct = os.environ.get("COLORTERM", "").lower()
    term = os.environ.get("TERM", "").lower()
    if ct in ("truecolor", "24bit"):
        return "truecolor"
    if "256" in term:
        return "256"
    if "color" in term or term in ("xterm", "screen", "tmux"):
        return "16"
    return "none"


_MODE = _detect_mode()


# ---------------------------------------------------------------------
# Low-level SGR emitters
# ---------------------------------------------------------------------

def _fg24(r: int, g: int, b: int) -> str:
    return f"\033[38;2;{r};{g};{b}m"


def _bg24(r: int, g: int, b: int) -> str:
    return f"\033[48;2;{r};{g};{b}m"


def _rgb_to_256(r: int, g: int, b: int) -> int:
    if r == g == b:
        if r < 8:
            return 16
        if r > 248:
            return 231
        return 232 + (r - 8) * 24 // 247
    return 16 + (r * 5 // 255) * 36 + (g * 5 // 255) * 6 + (b * 5 // 255)


def _fg256(r: int, g: int, b: int) -> str:
    return f"\033[38;5;{_rgb_to_256(r, g, b)}m"


def _bg256(r: int, g: int, b: int) -> str:
    return f"\033[48;5;{_rgb_to_256(r, g, b)}m"


def fg(r: int, g: int = None, b: int = None) -> str:
    """Foreground SGR. Accepts (r, g, b) or (0xRRGGBB)."""
    if g is None and b is None:
        value = int(r) & 0xFFFFFF
        r, g, b = (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF
    if _MODE == "truecolor":
        return _fg24(r, g, b)
    if _MODE == "256":
        return _fg256(r, g, b)
    return ""  # no color support


def bg(r: int, g: int = None, b: int = None) -> str:
    """Background SGR. Accepts (r, g, b) or (0xRRGGBB)."""
    if g is None and b is None:
        value = int(r) & 0xFFFFFF
        r, g, b = (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF
    if _MODE == "truecolor":
        return _bg24(r, g, b)
    if _MODE == "256":
        return _bg256(r, g, b)
    return ""


RESET = "\033[0m"
BOLD = "\033[1m"
UNBOLD = "\033[22m"
ITALIC = "\033[3m"
UNITALIC = "\033[23m"
UNDERLINE = "\033[4m"
UNUNDERLINE = "\033[24m"
STRIKE = "\033[9m"
UNSTRIKE = "\033[29m"
DIM = "\033[2m"
UNDIM = "\033[22m"
FG_RESET = "\033[39m"
BG_RESET = "\033[49m"


# ---------------------------------------------------------------------
# Public API (keeps the old shape: Color.Basic.fg, Color.Format.bold, ...)
# ---------------------------------------------------------------------

class Color:
    class Basic:
        fg = staticmethod(fg)
        bg = staticmethod(bg)
        reset = staticmethod(lambda: RESET)

        @staticmethod
        def rgb(r, g=None, b=None):
            if g is None and b is None:
                return int(r) & 0xFFFFFF
            return (int(r) << 16) | (int(g) << 8) | int(b)

        @staticmethod
        def ansi(code):
            return f"\033[{code}m"

    class Format:
        @staticmethod
        def bold(text):
            return f"{BOLD}{text}{UNBOLD}"

        @staticmethod
        def italic(text):
            return f"{ITALIC}{text}{UNITALIC}"

        @staticmethod
        def underline(text):
            return f"{UNDERLINE}{text}{UNUNDERLINE}"

        @staticmethod
        def strike(text):
            return f"{STRIKE}{text}{UNSTRIKE}"

        @staticmethod
        def dim(text):
            return f"{DIM}{text}{UNDIM}"

    class MessagePresets:
        @staticmethod
        def Info(text):
            return f"{BOLD}{fg(0, 170, 170)}{text}{RESET}"

        @staticmethod
        def Success(text):
            return f"{BOLD}{fg(0, 220, 120)}{text}{RESET}"

        @staticmethod
        def Warning(text):
            return f"{BOLD}{fg(255, 200, 0)}{text}{RESET}"

        @staticmethod
        def Error(text):
            return f"{BOLD}{fg(255, 80, 80)}{text}{RESET}"

    class ColorPresets:
        @staticmethod
        def _wrap(rgb, text):
            return f"{fg(*rgb)}{text}{FG_RESET}"

        @staticmethod
        def black(t):   return Color.ColorPresets._wrap((0, 0, 0), t)

        @staticmethod
        def red(t):     return Color.ColorPresets._wrap((220, 50, 50), t)

        @staticmethod
        def green(t):   return Color.ColorPresets._wrap((50, 200, 50), t)

        @staticmethod
        def yellow(t):  return Color.ColorPresets._wrap((230, 200, 60), t)

        @staticmethod
        def blue(t):    return Color.ColorPresets._wrap((80, 130, 255), t)

        @staticmethod
        def magenta(t): return Color.ColorPresets._wrap((220, 80, 220), t)

        @staticmethod
        def cyan(t):    return Color.ColorPresets._wrap((60, 220, 220), t)

        @staticmethod
        def white(t):   return Color.ColorPresets._wrap((230, 230, 230), t)

        @staticmethod
        def gray(t):    return Color.ColorPresets._wrap((150, 150, 150), t)

        @staticmethod
        def _ansi(code, text):
            return f"\033[{code}m{text}{FG_RESET}"

        @staticmethod
        def ansi_black(t):   return Color.ColorPresets._ansi(30, t)

        @staticmethod
        def ansi_red(t):     return Color.ColorPresets._ansi(31, t)

        @staticmethod
        def ansi_green(t):   return Color.ColorPresets._ansi(32, t)

        @staticmethod
        def ansi_yellow(t):  return Color.ColorPresets._ansi(33, t)

        @staticmethod
        def ansi_blue(t):    return Color.ColorPresets._ansi(34, t)

        @staticmethod
        def ansi_magenta(t): return Color.ColorPresets._ansi(35, t)

        @staticmethod
        def ansi_cyan(t):    return Color.ColorPresets._ansi(36, t)

        @staticmethod
        def ansi_white(t):   return Color.ColorPresets._ansi(37, t)

        @staticmethod
        def ansi_bright_black(t):   return Color.ColorPresets._ansi(90, t)

        @staticmethod
        def ansi_bright_red(t):     return Color.ColorPresets._ansi(91, t)

        @staticmethod
        def ansi_bright_green(t):   return Color.ColorPresets._ansi(92, t)

        @staticmethod
        def ansi_bright_yellow(t):  return Color.ColorPresets._ansi(93, t)

        @staticmethod
        def ansi_bright_blue(t):    return Color.ColorPresets._ansi(94, t)

        @staticmethod
        def ansi_bright_magenta(t): return Color.ColorPresets._ansi(95, t)

        @staticmethod
        def ansi_bright_cyan(t):    return Color.ColorPresets._ansi(96, t)

        @staticmethod
        def ansi_bright_white(t):   return Color.ColorPresets._ansi(97, t)

    class Style:
        @staticmethod
        def style(text, fg=None, bg=None, bold=False, underline=False):
            parts = []
            if fg is not None:
                parts.append(Color.Basic.fg(fg))
            if bg is not None:
                parts.append(Color.Basic.bg(bg))
            if bold:
                parts.append(BOLD)
            if underline:
                parts.append(UNDERLINE)
            parts.append(text)
            parts.append(RESET)
            return "".join(parts)

    class Utility:
        @staticmethod
        def hex_to_rgb(hex_code):
            if not 0 <= hex_code <= 0xFFFFFF:
                raise ValueError("hex_code must be between 0 and 2^24-1")
            value = int(hex_code)
            return (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF

        @staticmethod
        def rgb_to_hex(r, g, b):
            for name, v in (("red", r), ("green", g), ("blue", b)):
                if not 0 <= v <= 255:
                    raise ValueError(f"{name} must be between 0 and 255")
            return (int(r) << 16) | (int(g) << 8) | int(b)

        @staticmethod
        def gradient(text, start_color, end_color, mode="fg"):
            if mode not in ("fg", "bg"):
                raise ValueError("mode must be 'fg' or 'bg'")
            r1, g1, b1 = Color.Utility.hex_to_rgb(start_color)
            r2, g2, b2 = Color.Utility.hex_to_rgb(end_color)
            n = len(text)
            if n == 0:
                return ""
            if n == 1:
                code = fg(r1, g1, b1) if mode == "fg" else bg(r1, g1, b1)
                return code + text + RESET
            out = []
            denom = n - 1
            for i, ch in enumerate(text):
                t = i / denom
                r = round(r1 + (r2 - r1) * t)
                g = round(g1 + (g2 - g1) * t)
                b = round(b1 + (b2 - b1) * t)
                out.append(fg(r, g, b) if mode == "fg" else bg(r, g, b))
                out.append(ch)
            out.append(RESET)
            return "".join(out)

        @staticmethod
        def colorize(color):
            r, g, b = Color.Utility.hex_to_rgb(color)
            return fg(r, g, b)


# ---------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------
#
# Order of operations (each step is a plain string replace, no regex
# lookbehinds, no placeholders that can leak):
#
#   1. Split into lines.
#   2. Track fenced code blocks line-by-line so nothing inside is parsed.
#   3. For each non-code line, apply inline transforms in a fixed order.
#   4. Assemble.
# ---------------------------------------------------------------------

class Markdown:
    _HEADER_COLORS = {
        1: (255, 200, 60),
        2: (80, 200, 220),
        3: (130, 180, 255),
        4: (200, 180, 255),
        5: (200, 200, 200),
        6: (160, 160, 160),
    }

    # --- inline transforms -------------------------------------------

    @staticmethod
    def _inline(text: str) -> str:
        # 1. Inline code: `...`
        out = []
        i = 0
        n = len(text)
        while i < n:
            if text[i] == "`":
                j = text.find("`", i + 1)
                if j != -1:
                    body = text[i + 1:j]
                    out.append(f"{DIM}{fg(255, 220, 120)}{body}{RESET}")
                    i = j + 1
                    continue
            out.append(text[i])
            i += 1
        text = "".join(out)

        # 2. Bold+italic ***...***
        text = Markdown._wrap_pairs(text, "***", "***",
                                    lambda s: f"{BOLD}{ITALIC}{s}{UNITALIC}{UNBOLD}")
        # 3. Bold **...** and __...__
        text = Markdown._wrap_pairs(text, "**", "**",
                                    lambda s: f"{BOLD}{s}{UNBOLD}")
        text = Markdown._wrap_pairs(text, "__", "__",
                                    lambda s: f"{BOLD}{s}{UNBOLD}")
        # 4. Italic *...* and _..._
        text = Markdown._wrap_pairs(text, "*", "*",
                                    lambda s: f"{ITALIC}{s}{UNITALIC}")
        text = Markdown._wrap_pairs(text, "_", "_",
                                    lambda s: f"{ITALIC}{s}{UNITALIC}")

        # 4.5 Strikethrough ~~...~~
        text = Markdown._wrap_pairs(text, "~~", "~~",
                            lambda s: f"{STRIKE}{s}{UNSTRIKE}")

        # 5. Links [label](url)
        text = Markdown._links(text)
        return text

    @staticmethod
    def _wrap_pairs(text: str, open_m: str, close_m: str, wrap) -> str:
        """Replace non-overlapping open_m ... close_m with wrap(inner)."""
        result = []
        i = 0
        n = len(text)
        while i < n:
            if text.startswith(open_m, i):
                j = text.find(close_m, i + len(open_m))
                if j != -1 and j > i + len(open_m):
                    inner = text[i + len(open_m):j]
                    result.append(wrap(inner))
                    i = j + len(close_m)
                    continue
            result.append(text[i])
            i += 1
        return "".join(result)

    @staticmethod
    def _links(text: str) -> str:
        result = []
        i = 0
        n = len(text)
        while i < n:
            if text[i] == "[":
                close = text.find("]", i + 1)
                if close != -1 and close + 1 < n and text[close + 1] == "(":
                    end = text.find(")", close + 2)
                    if end != -1:
                        label = text[i + 1:close]
                        url = text[close + 2:end]
                        result.append(f"{UNDERLINE}{label}{UNUNDERLINE}")
                        result.append(f"{DIM} ({url}){UNDIM}")
                        i = end + 1
                        continue
            result.append(text[i])
            i += 1
        return "".join(result)

    # --- line transforms ---------------------------------------------

    @staticmethod
    def _is_hr(line: str) -> bool:
        s = line.strip()
        if len(s) < 3:
            return False
        for ch in ("-", "*", "_"):
            if s == ch * len(s) and len(s) >= 3:
                return True
        return False

    @staticmethod
    def _header(line: str) -> str | None:
        s = line.lstrip()
        hashes = 0
        while hashes < len(s) and s[hashes] == "#":
            hashes += 1
        if 1 <= hashes <= 6 and hashes < len(s) and s[hashes] == " ":
            title = s[hashes + 1:].strip()
            r, g, b = Markdown._HEADER_COLORS[hashes]
            colored = f"{fg(r, g, b)}{BOLD}{title}{UNBOLD}{RESET}"
            if hashes == 1:
                rule = f"{fg(r, g, b)}{'═' * min(len(title), 60)}{RESET}"
                return f"\n{colored}\n{rule}"
            if hashes == 2:
                rule = f"{fg(r, g, b)}{'─' * min(len(title), 60)}{RESET}"
                return f"\n{colored}\n{rule}"
            return f"\n{colored}"
        return None

    @staticmethod
    def _bullet(line: str) -> str | None:
        stripped = line.lstrip()
        indent = line[:len(line) - len(stripped)]
        if len(stripped) >= 2 and stripped[0] in "-*+" and stripped[1] == " ":
            content = stripped[2:]
            bullet = f"{fg(150, 150, 150)}•{RESET}"
            return f"{indent}  {bullet} {content}"
        return None

    @staticmethod
    def _ordered(line: str) -> str | None:
        stripped = line.lstrip()
        indent = line[:len(line) - len(stripped)]
        i = 0
        while i < len(stripped) and stripped[i].isdigit():
            i += 1
        if i > 0 and i + 1 < len(stripped) and stripped[i] == "." and stripped[i + 1] == " ":
            num = stripped[:i]
            content = stripped[i + 2:]
            num_colored = f"{fg(150, 150, 150)}{num}.{RESET}"
            return f"{indent}  {num_colored} {content}"
        return None

    @staticmethod
    def _quote(line: str) -> str | None:
        stripped = line.lstrip()
        if stripped.startswith("> "):
            return f"{DIM}│{UNDIM} {stripped[2:]}"
        if stripped == ">":
            return f"{DIM}│{UNDIM}"
        return None

    # --- main entry --------------------------------------------------

    @staticmethod
    def render(text: str) -> str:
        if not text:
            return text
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        lines = text.split("\n")
        out: list[str] = []
        in_fence = False
        fence_lang = ""

        for line in lines:
            stripped = line.lstrip()

            # Fenced code block boundaries
            if stripped.startswith("```"):
                if not in_fence:
                    in_fence = True
                    fence_lang = stripped[3:].strip()
                    if fence_lang:
                        out.append(f"{DIM}{fence_lang}{UNDIM}")
                    continue
                else:
                    in_fence = False
                    fence_lang = ""
                    continue

            if in_fence:
                # Every line inside a fence gets a uniform code-block style
                out.append(f"{DIM}{fg(220, 220, 170)} {line}{RESET}")
                continue

            # Horizontal rule
            if Markdown._is_hr(line):
                out.append(f"{DIM}{'─' * 60}{UNDIM}")
                continue

            # Header
            h = Markdown._header(line)
            if h is not None:
                out.append(h)
                continue

            # Blockquote
            q = Markdown._quote(line)
            if q is not None:
                out.append(Markdown._inline(q))
                continue

            # Lists
            ul = Markdown._bullet(line)
            if ul is not None:
                out.append(Markdown._inline(ul))
                continue
            ol = Markdown._ordered(line)
            if ol is not None:
                out.append(Markdown._inline(ol))
                continue

            # Plain paragraph line
            out.append(Markdown._inline(line))

        return "\n".join(out)


# Convenience alias so both `Markdown.render` and `render_markdown` work
def render_markdown(text: str) -> str:
    return Markdown.render(text)


if __name__ == "__main__":
    sample = (
        "# Heading 1\n"
        "## Heading 2\n\n"
        "Plain **bold** and *italic* and `code`.\n\n"
        "- bullet one\n"
        "- bullet two\n\n"
        "> a quote\n\n"
        "A [link](https://example.com).\n\n"
        "```python\nprint('hello')\n```\n\n"
        "---\n"
    )
    print(Markdown.render(sample))