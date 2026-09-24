from prompt_toolkit.formatted_text import FormattedText
from lib_color import Color, RESET
from . import config


BUILTIN_THEME = {
    "banner": "100,200,255",
    "version": "200,225,100",
    "prompt": "100,200,255",
    "continuation": "110,110,110",
    "error": "255,80,80",
    "warning": "255,200,0",
    "success": "0,220,120",
    "info": "0,170,170",
    "dim": "120,120,120",
    "chat_num": "255,215,0",
    "chat_id": "110,110,110",
    "menu_action": "200,180,255",
    "menu_key": "180,180,180",
    "link": "100,200,255",
}


def get_theme() -> dict:
    themes = config.load_themes()
    name = config.get_theme_name()
    base = themes.get("default", BUILTIN_THEME)
    chosen = themes.get(name, base)
    merged = dict(BUILTIN_THEME)
    merged.update(base)
    merged.update(chosen)
    return merged


def theme_rgb(name: str) -> tuple[int, int, int] | None:
    value = get_theme().get(name)
    if not value:
        return None
    try:
        r, g, b = (int(x.strip()) for x in value.split(","))
    except (ValueError, AttributeError):
        return None
    return r, g, b


def tag(name: str, text: str) -> str:
    """ANSI-colored text, for use with print()."""
    rgb = theme_rgb(name)
    if rgb is None:
        return text
    r, g, b = rgb
    return f"{Color.Basic.fg(r, g, b)}{text}{RESET}"


def prompt_tag(name: str, text: str) -> FormattedText:
    """prompt_toolkit FormattedText with the theme color. Use for prompts only."""
    rgb = theme_rgb(name)
    if rgb is None:
        return FormattedText([("", text)])
    r, g, b = rgb
    return FormattedText([(f"#{r:02x}{g:02x}{b:02x}", text)])