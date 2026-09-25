import re
from lib_color import Color, Markdown, RESET
from .debug import dbg
from .copy import ContainerStore, extract_containers


_RAW_OPEN = "\\RAW"
_RAW_CLOSE = "\\RAWEND"
_PLACEHOLDER_RE = re.compile(r"\x00RAW(\d+)\x00")


def render_markdown(text: str, store: ContainerStore | None = None) -> str:
    # 0. Extract copy containers first, if a store was provided.
    if store is not None:
        text = extract_containers(text, store)

    # 1. Extract \RAW...\RAWEND blocks into placeholders
    raw_blocks: list[str] = []

    def _stash(m):
        raw_blocks.append(m.group(1))
        dbg("raw block stashed", len(m.group(1)))
        return f"\x00RAW{len(raw_blocks) - 1}\x00"

    text = re.sub(r"\\RAW(.*?)\\RAWEND", _stash, text)

    if _RAW_OPEN in text:
        new_lines = []
        for line in text.split("\n"):
            if _RAW_OPEN in line and not _PLACEHOLDER_RE.search(line):
                idx = line.index(_RAW_OPEN)
                prefix = line[:idx]
                rest = line[idx + len(_RAW_OPEN):]
                raw_blocks.append(rest)
                new_lines.append(prefix + f"\x00RAW{len(raw_blocks) - 1}\x00")
            else:
                new_lines.append(line)
        text = "\n".join(new_lines)

    # 2. Normal pipeline
    processed = Markdown.render(_apply_custom(text))

    # 3. Restore raw blocks verbatim
    def _restore(m):
        return raw_blocks[int(m.group(1))]

    processed = _PLACEHOLDER_RE.sub(_restore, processed)
    return processed


def _apply_custom(text: str) -> str:
    lines = text.split("\n")
    rendered_lines = [_apply_custom_line(line) + RESET for line in lines]
    return "\n".join(rendered_lines)


def _emit_color_fg(value: int) -> str:
    r = (value >> 16) & 0xFF
    g = (value >> 8) & 0xFF
    b = value & 0xFF
    return Color.Basic.fg(r, g, b)


def _emit_color_bg(value: int) -> str:
    r = (value >> 16) & 0xFF
    g = (value >> 8) & 0xFF
    b = value & 0xFF
    return Color.Basic.bg(r, g, b)


def _apply_custom_line(line: str) -> str:
    result = []
    stack: list[str] = []

    def open_scope(code: str):
        stack.append(code)
        result.append(code)

    def close_scope():
        if not stack:
            result.append(RESET)
            return
        stack.pop()
        result.append(RESET)
        if stack:
            result.append(stack[-1])

    def reset_all():
        stack.clear()
        result.append(RESET)

    i = 0
    n = len(line)
    while i < n:
        if line[i] == "\\" and i + 1 < n:
            if line.startswith("\\R!", i):
                reset_all()
                i += 3
                continue

            if line.startswith("\\R", i):
                close_scope()
                i += 2
                continue

            if line.startswith("\\U:on", i):
                result.append("\033[4m")
                i += 5
                continue

            if line.startswith("\\U:off", i):
                result.append("\033[24m")
                i += 6
                continue

            if line.startswith("\\Cx{", i):
                j = i + 4
                k = line.find("}", j)
                if k != -1 and k - j == 6 and all(
                    c in "0123456789abcdefABCDEF" for c in line[j:k]
                ):
                    value = int(line[j:k], 16)
                    code = _emit_color_fg(value)
                    open_scope(code)
                    dbg("hex fg", (hex(value), len(stack)))
                    i = k + 1
                    continue

            if line.startswith("\\Bx{", i):
                j = i + 4
                k = line.find("}", j)
                if k != -1 and k - j == 6 and all(
                    c in "0123456789abcdefABCDEF" for c in line[j:k]
                ):
                    value = int(line[j:k], 16)
                    code = _emit_color_bg(value)
                    open_scope(code)
                    dbg("hex bg", (hex(value), len(stack)))
                    i = k + 1
                    continue

            if line.startswith("\\C:{", i):
                j = i + 4
                k = line.find("}", j)
                if k != -1:
                    token = line[j:k].lower()
                    if token.isdigit():
                        idx = int(token)
                        if 0 <= idx <= 255:
                            code = f"\033[38;5;{idx}m"
                            open_scope(code)
                            dbg("256 fg", (idx, len(stack)))
                        else:
                            dbg("256 fg out of range", idx)
                    else:
                        fn = getattr(Color.ColorPresets, token, None)
                        if fn:
                            sentinel = "\x00"
                            wrapped = fn(sentinel)
                            if sentinel in wrapped:
                                code = wrapped.split(sentinel)[0]
                                open_scope(code)
                                dbg("preset fg", (token, len(stack)))
                        else:
                            dbg("preset fg unknown", token)
                    i = k + 1
                    continue

            if line.startswith("\\B:{", i):
                j = i + 4
                k = line.find("}", j)
                if k != -1:
                    token = line[j:k].lower()
                    if token.isdigit():
                        idx = int(token)
                        if 0 <= idx <= 255:
                            code = f"\033[48;5;{idx}m"
                            open_scope(code)
                            dbg("256 bg", (idx, len(stack)))
                        else:
                            dbg("256 bg out of range", idx)
                    else:
                        fn = getattr(Color.ColorPresets, token, None)
                        if fn:
                            sentinel = "\x00"
                            wrapped = fn(sentinel)
                            if sentinel in wrapped:
                                prefix = wrapped.split(sentinel)[0]
                                prefix = prefix.replace("[38;2;", "[48;2;")
                                prefix = prefix.replace("[38;5;", "[48;5;")
                                open_scope(prefix)
                                dbg("preset bg", (token, len(stack)))
                        else:
                            dbg("preset bg unknown", token)
                    i = k + 1
                    continue

        result.append(line[i])
        i += 1
    return "".join(result)