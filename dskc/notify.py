"""Desktop notification helpers. Fails silently on unsupported systems."""

import shutil
import subprocess
import sys

from . import config
from .debug import dbg


def _linux_notify(title: str, body: str) -> bool:
    if shutil.which("notify-send") is None:
        dbg("notify: notify-send not found")
        return False
    try:
        subprocess.run(
            ["notify-send", "-a", "DSKC", title, body],
            timeout=2,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as e:  # noqa: BLE001
        dbg("notify: failed", str(e))
        return False


def _macos_notify(title: str, body: str) -> bool:
    if shutil.which("osascript") is None:
        return False
    try:
        script = f'display notification "{body}" with title "{title}"'
        subprocess.run(
            ["osascript", "-e", script],
            timeout=2,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as e:  # noqa: BLE001
        dbg("notify: failed", str(e))
        return False


def notify(title: str, body: str) -> bool:
    """Send a desktop notification if enabled. Returns True on success."""
    if not config.get_notifications():
        return False
    if sys.platform.startswith("linux"):
        return _linux_notify(title, body)
    if sys.platform == "darwin":
        return _macos_notify(title, body)
    dbg("notify: unsupported platform", sys.platform)
    return False