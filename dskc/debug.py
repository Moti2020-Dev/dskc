import sys
from lib_color import Color, RESET


def is_debug() -> bool:
    return "--debug" in sys.argv


def dbg(label: str, value=None):
    """Print a debug line when --debug is active."""
    if not is_debug():
        return
    msg = f"[DEBUG] {label}"
    if value is not None:
        msg += f" = {value!r}"
    print(f"{Color.Basic.fg(120, 120, 200)}{msg}{RESET}")