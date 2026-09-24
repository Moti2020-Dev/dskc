from lib_color import Color
from . import config
from .debug import dbg
from .sessions import (
    ask_settings, ask_input,
    S_CANCEL, S_BACK, S_AUTOSEND, S_THEME, S_VERSION,
)
from .themes import tag


def _show_settings_menu():
    autosend = config.get_autosend()
    if autosend:
        preview = autosend.replace("\n", " ")
        if len(preview) > 40:
            preview = preview[:37] + "..."
        autosend_line = tag("version", preview)
    else:
        autosend_line = tag("dim", "(none)")

    print()
    print("  " + tag("banner", Color.Format.bold("◆  Settings")))
    print("  " + tag("dim", "─" * 46))
    print("   " + tag("menu_action", "a") + tag("dim", "  autosend: ") + autosend_line)
    print("   " + tag("menu_action", "t") + tag("dim", "  theme: ") + tag("version", config.get_theme_name()))
    print("   " + tag("menu_action", "v") + tag("dim", "  version: ") + tag("version", config.get_version()))
    print("   " + tag("menu_key", "b") + tag("dim", "  back"))
    print()


async def settings_menu() -> None:
    while True:
        _show_settings_menu()

        try:
            raw = await ask_settings()
        except EOFError:
            print()
            raise SystemExit(0)
        except KeyboardInterrupt:
            print()
            continue

        if raw == S_BACK or raw == S_CANCEL:
            dbg("settings: back")
            return
        if raw == "\x00QUIT":
            raise SystemExit(0)

        if raw == S_AUTOSEND:
            try:
                print(Color.Format.dim(
                    "  Enter autosend message. Enter = submit, Ctrl+O = newline. Empty = clear."
                ))
                new_text = (await ask_input("Autosend: ")).strip()
            except EOFError:
                raise SystemExit(0)
            except KeyboardInterrupt:
                print()
                continue
            if new_text == S_CANCEL:
                continue
            config.set_autosend(new_text)
            dbg("settings: autosend set", len(new_text))
            if new_text:
                print(Color.MessagePresets.Success("  Autosend set."))
            else:
                print(Color.MessagePresets.Success("  Autosend cleared."))
            continue

        if raw == S_THEME:
            themes = config.load_themes()
            names = list(themes.keys())
            print(tag("dim", "  Available themes:"))
            for i, name in enumerate(names, 1):
                marker = " *" if name == config.get_theme_name() else ""
                print(f"    {i}. {name}{marker}")
            try:
                choice = (await ask_input("Pick theme: ")).strip()
            except EOFError:
                raise SystemExit(0)
            except KeyboardInterrupt:
                print()
                continue
            if choice == S_CANCEL or not choice:
                continue
            if choice.isdigit() and 1 <= int(choice) <= len(names):
                config.set_theme_name(names[int(choice) - 1])
                dbg("settings: theme set", names[int(choice) - 1])
                print(Color.MessagePresets.Success(f"  Theme set to {names[int(choice) - 1]}."))
            else:
                print(Color.MessagePresets.Error("  Invalid choice."))
            continue

        if raw == S_VERSION:
            try:
                current = config.get_version()
                print(Color.Format.dim(f"  Current version: {current}"))
                new_ver = (await ask_input("New version (empty = keep): ")).strip()
            except EOFError:
                raise SystemExit(0)
            except KeyboardInterrupt:
                print()
                continue
            if new_ver and new_ver != S_CANCEL:
                config.set_version(new_ver)
                dbg("settings: version set", new_ver)
                print(Color.MessagePresets.Success(f"  Version set to {new_ver}."))
            continue

        # Unknown input at settings
        print(Color.MessagePresets.Error("  Invalid input."))