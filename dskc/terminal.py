"""Terminal-level escape helpers: window title."""

import sys
from .debug import dbg


def set_title(text: str):
    """Set the terminal window title via OSC 0."""
    try:
        sys.stdout.write(f"\033]0;{text}\007")
        sys.stdout.flush()
        dbg("terminal title set", text)
    except Exception as e:  # noqa: BLE001
        dbg("terminal title failed", str(e))


def reset_title():
    set_title("DSKC")