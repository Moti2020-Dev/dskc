"""
Reference content for chat-prompt commands.
Single source of truth for the autosend template and the syntax tables.
"""

AUTOSEND_TEMPLATE = r"""You are replying to a terminal client that renders ANSI colors and markdown.

Markdown: # headers, **bold**, *italic*, ~~strikethrough~~, `code`, ``` fenced blocks ```, - lists, > quotes, [links](url).

Color codes:
  \C:{preset}text     foreground preset
  \B:{preset}text     background preset
  \C:{N}text          foreground 256-palette index (0-255)
  \B:{N}text          background 256-palette index (0-255)
  \Cx{RRGGBB}text     foreground hex
  \Bx{RRGGBB}text     background hex
  \U:on / \U:off      underline
  \R                  close innermost color
  \R!                 reset all colors

Braces wrap the preset name, index, or hex ONLY — never the text.
Reset is automatic at every newline.

Nesting works: \C:{cyan}outer \C:{red}inner\R back to cyan\R

To show a code literally without triggering it, wrap it in \RAW...\RAWEND:
  \RAW\C:{cyan}text\RAWEND shows the literal codes.
  \C:{cyan}text actually colors the text.
Raw blocks don't span lines, and don't nest.

Presets: black, red, green, yellow, blue, magenta, cyan, white, gray,
plus ansi_* and ansi_bright_* variants.

Use color tastefully — headings, warnings, emphasis, status. Not every word.

Confirm and wait for my next message."""


PRESETS_ORDERED = [
    "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white", "gray",
    "ansi_black", "ansi_red", "ansi_green", "ansi_yellow",
    "ansi_blue", "ansi_magenta", "ansi_cyan", "ansi_white",
    "ansi_bright_black", "ansi_bright_red", "ansi_bright_green",
    "ansi_bright_yellow", "ansi_bright_blue", "ansi_bright_magenta",
    "ansi_bright_cyan", "ansi_bright_white",
]


KEY_BINDINGS = [
    ("Menu",     "1-9 + Enter", "Open chat"),
    ("Menu",     "0 + Enter",   "New chat"),
    ("Menu",     "r",           "Rename"),
    ("Menu",     "d",           "Delete"),
    ("Menu",     "x",           "Export"),
    ("Menu",     "s",           "Settings"),
    ("Menu",     "q",           "Quit"),
    ("Settings", "a",           "Edit autosend"),
    ("Settings", "t",           "Pick theme"),
    ("Settings", "v",           "Change version"),
    ("Settings", "b",           "Back"),
    ("Chat",     "Enter",       "Send message"),
    ("Chat",     "Ctrl+O",      "Insert newline"),
    ("Chat",     "Esc",         "Cancel, back to menu"),
    ("Chat",     "Ctrl+C",      "Back to menu"),
    ("Chat",     "Ctrl+D",      "Quit program"),
]


SYNTAX_ROWS = [
    (r"\C:{preset}text",   "Foreground preset"),
    (r"\B:{preset}text",   "Background preset"),
    (r"\C:{N}text",        "Foreground 256-palette index (0-255)"),
    (r"\B:{N}text",        "Background 256-palette index (0-255)"),
    (r"\Cx{RRGGBB}text",   "Foreground hex"),
    (r"\Bx{RRGGBB}text",   "Background hex"),
    (r"\U:on",             "Start underline"),
    (r"\U:off",            "End underline"),
    (r"\R",                "Close innermost color"),
    (r"\R!",               "Reset all colors"),
    (r"\RAW...\RAWEND",    "Show codes literally"),
]


CHAT_COMMANDS = [
    (":help",        "Show this list"),
    (":colors",      "Show every preset rendered in itself"),
    (":syntax",      "Show the custom escape reference"),
    (":keys",        "Show all key bindings"),
    (":aitemplate",  "Print the autosend template"),
    (":export",      "Export this chat to markdown"),
    (":retry",       "Resend the last message"),
    (":edit",        "Edit the last message"),
    (":undo",        "Remove the last exchange from local history"),
    ("stop",         "Quit the program"),
    ("quit / exit",  "Back to the menu"),
]


# ---------------------------------------------------------------------
# Printers
# ---------------------------------------------------------------------

def _header(text: str):
    from lib_color import RESET, Color

    from .themes import theme_rgb
    rgb = theme_rgb("banner") or (100, 200, 255)
    r, g, b = rgb
    print()
    print(f"  {Color.Basic.fg(r, g, b)}{Color.Format.bold(text)}{RESET}")
    print(f"  {Color.Basic.fg(120, 120, 120)}{'─' * 46}{RESET}")


def _kv(key: str, value: str, key_width: int = 22):
    from lib_color import RESET, Color

    from .themes import theme_rgb
    key_rgb = theme_rgb("menu_action") or (200, 180, 255)
    val_rgb = theme_rgb("dim") or (120, 120, 120)
    kr, kg, kb = key_rgb
    vr, vg, vb = val_rgb
    print(
        f"   {Color.Basic.fg(kr, kg, kb)}{key.ljust(key_width)}{RESET}"
        f"{Color.Basic.fg(vr, vg, vb)}{value}{RESET}"
    )


def print_help():
    _header("Chat commands")
    for cmd, desc in CHAT_COMMANDS:
        _kv(cmd, desc)


def print_syntax():
    _header("Color syntax")
    for syntax, desc in SYNTAX_ROWS:
        _kv(syntax, desc)
    print()
    from lib_color import RESET, Color

    from .themes import theme_rgb
    rgb = theme_rgb("dim") or (120, 120, 120)
    r, g, b = rgb
    print(f"  {Color.Basic.fg(r, g, b)}Presets:{RESET}")
    print(f"  {Color.Basic.fg(r, g, b)}  {', '.join(PRESETS_ORDERED[:9])}{RESET}")
    print(f"  {Color.Basic.fg(r, g, b)}  plus ansi_* and ansi_bright_* variants{RESET}")
    print()


def print_keys():
    _header("Key bindings")
    current_context = None
    for context, key, action in KEY_BINDINGS:
        if context != current_context:
            print()
            from lib_color import RESET, Color

            from .themes import theme_rgb
            rgb = theme_rgb("info") or (0, 170, 170)
            r, g, b = rgb
            print(f"   {Color.Basic.fg(r, g, b)}{context}{RESET}")
            current_context = context
        _kv(key, action)


def print_colors():
    _header("Presets")
    from lib_color import Color
    for name in PRESETS_ORDERED:
        fn = getattr(Color.ColorPresets, name, None)
        if fn is None:
            continue
        print(f"   {fn(name.ljust(20))}")

    _header("256-color palette")
    # 16 rows of 16 cells, each cell shows the index on its own background
    for row in range(16):
        line = "   "
        for col in range(16):
            idx = row * 16 + col
            bg = f"\033[48;5;{idx}m"
            # choose readable foreground based on luminance-ish heuristic
            fg = "\033[38;5;0m" if idx not in (0, 16, 232) else "\033[38;5;15m"
            line += f"{bg}{fg}{idx:>4}\033[0m"
        print(line)
    print()


def print_aitemplate():
    _header("Autosend template")
    print()
    # Print raw, not rendered. The point is to copy this text.
    print(AUTOSEND_TEMPLATE)
    print()
    from lib_color import RESET, Color

    from .themes import theme_rgb
    rgb = theme_rgb("dim") or (120, 120, 120)
    r, g, b = rgb
    print(f"  {Color.Basic.fg(r, g, b)}Copy the block above, then use s -> a to set it.{RESET}")
    print()


def get_aitemplate() -> str:
    return AUTOSEND_TEMPLATE


# ---------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------

def dispatch(cmd: str, args: str = "") -> bool:
    """Handle a :command from the chat prompt. Returns True if handled."""
    table = {
        "help":       print_help,
        "colors":     print_colors,
        "syntax":     print_syntax,
        "keys":       print_keys,
        "aitemplate": print_aitemplate,
    }
    fn = table.get(cmd)
    if fn is None:
        return False
    fn()
    return True