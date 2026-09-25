import pathlib

from lib_color import Color, strip_ansi

from .debug import dbg

MAX_BYTES = 200_000


def _parse_load_args(args: str) -> tuple[set[str], str | None]:
    flags: set[str] = set()
    words: list[str] = []
    for token in args.split():
        if token.startswith("--"):
            flags.add(token)
        else:
            words.append(token)
    name = " ".join(words) if words else None
    return flags, name


def read_load_file(args: str) -> str | None:
    flags, name = _parse_load_args(args)

    if name is None:
        print(Color.MessagePresets.Warning("  Usage: :load <file>"))
        return None

    path = pathlib.Path(name).expanduser()
    if not path.exists():
        print(Color.MessagePresets.Error(f"  File not found: {path}"))
        return None
    if not path.is_file():
        print(Color.MessagePresets.Error(f"  Not a file: {path}"))
        return None

    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(Color.MessagePresets.Error(
            f"  {path} is not valid UTF-8 (binary file?)"
        ))
        return None
    except OSError as e:
        print(Color.MessagePresets.Error(f"  Load failed: {e}"))
        return None

    text = strip_ansi(raw).strip()
    if not text:
        print(Color.MessagePresets.Warning(f"  {path} is empty after stripping."))
        return None

    size = len(text.encode("utf-8"))
    if size > MAX_BYTES and "--force" not in flags:
        kb = size // 1024
        print(Color.MessagePresets.Warning(
            f"  Refusing to send {kb} KB without --force."
        ))
        return None

    dbg("load read", (str(path), size))
    print(Color.MessagePresets.Info(
        f"  Loaded {len(text)} chars from {path}"
    ))
    return text