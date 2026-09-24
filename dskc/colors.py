import re
from lib_color import Color, Markdown, RESET


def render_markdown(text: str) -> str:
    return Markdown.render(_apply_custom(text))


def _apply_custom(text: str) -> str:
    lines = text.split("\n")
    rendered_lines = [_apply_custom_line(line) + RESET for line in lines]
    return "\n".join(rendered_lines)


def _apply_custom_line(line: str) -> str:
    result = []
    i = 0
    n = len(line)
    while i < n:
        if line[i] == "\\" and i + 1 < n:
            if line.startswith("\\R", i):
                result.append(RESET)
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
                    r = (value >> 16) & 0xFF
                    g = (value >> 8) & 0xFF
                    b = value & 0xFF
                    result.append(Color.Basic.fg(r, g, b))
                    i = k + 1
                    continue

            if line.startswith("\\Bx{", i):
                j = i + 4
                k = line.find("}", j)
                if k != -1 and k - j == 6 and all(
                    c in "0123456789abcdefABCDEF" for c in line[j:k]
                ):
                    value = int(line[j:k], 16)
                    r = (value >> 16) & 0xFF
                    g = (value >> 8) & 0xFF
                    b = value & 0xFF
                    result.append(Color.Basic.bg(r, g, b))
                    i = k + 1
                    continue

            if line.startswith("\\C:{", i):
                j = i + 4
                k = line.find("}", j)
                if k != -1:
                    preset = line[j:k].lower()
                    fn = getattr(Color.ColorPresets, preset, None)
                    if fn:
                        sentinel = "\x00"
                        wrapped = fn(sentinel)
                        if sentinel in wrapped:
                            result.append(wrapped.split(sentinel)[0])
                    i = k + 1
                    continue

            if line.startswith("\\B:{", i):
                j = i + 4
                k = line.find("}", j)
                if k != -1:
                    preset = line[j:k].lower()
                    fn = getattr(Color.ColorPresets, preset, None)
                    if fn:
                        sentinel = "\x00"
                        wrapped = fn(sentinel)
                        if sentinel in wrapped:
                            prefix = wrapped.split(sentinel)[0]
                            prefix = prefix.replace("[38;2;", "[48;2;")
                            prefix = prefix.replace("[38;5;", "[48;5;")
                            result.append(prefix)
                    i = k + 1
                    continue

        result.append(line[i])
        i += 1
    return "".join(result)