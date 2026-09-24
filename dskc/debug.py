# dskc/debug.py
import sys
from lib_color import Color, RESET

_SEEN = set()


def is_debug() -> bool:
    return "--debug" in sys.argv


def dbg(label: str, value=None, once: bool = False):
    if not is_debug():
        return
    if once:
        key = (label, repr(value))
        if key in _SEEN:
            return
        _SEEN.add(key)
    msg = f"[DEBUG] {label}"
    if value is not None:
        msg += f" = {value!r}"
    print(f"{Color.Basic.fg(120, 120, 200)}{msg}{RESET}")