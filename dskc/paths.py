import pathlib

_HERE = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = _HERE.parent

CHATS_FILE = PROJECT_ROOT / "chats.json"
CONFIG_FILE = PROJECT_ROOT / "config.json"
THEMES_FILE = PROJECT_ROOT / "themes.json"
HISTORY_DIR = PROJECT_ROOT / "history"
HISTORY_DIR.mkdir(exist_ok=True)