from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.formatted_text import FormattedText
from .themes import prompt_tag

S_QUIT     = "\x00QUIT"
S_CANCEL   = "\x00CANCEL"
S_RENAME   = "\x00RENAME"
S_DELETE   = "\x00DELETE"
S_EXPORT   = "\x00EXPORT"
S_VERSION  = "\x00VERSION"
S_THEME    = "\x00THEME"
S_AUTOSEND = "\x00AUTOSEND"

_ACTION_BINDINGS = [
    ("r", S_RENAME), ("d", S_DELETE), ("x", S_EXPORT),
    ("v", S_VERSION), ("t", S_THEME),
    ("e", S_AUTOSEND), ("a", S_AUTOSEND),
    ("q", S_QUIT),
]


def _continuation(width, line_number, is_soft_wrap):
    return prompt_tag("continuation", "  | ")


def _action_handler(sentinel, char):
    def handler(event):
        if event.current_buffer.text:
            event.current_buffer.insert_text(char)
        else:
            event.app.exit(result=sentinel)
    return handler


def build_menu_session() -> PromptSession:
    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        event.current_buffer.validate_and_handle()

    @kb.add("c-o")
    def _(event):
        event.current_buffer.insert_text("\n")

    @kb.add("escape", eager=True)
    def _(event):
        event.app.exit(result=S_CANCEL)

    for key, sentinel in _ACTION_BINDINGS:
        kb.add(key)(_action_handler(sentinel, key))

    return PromptSession(
        key_bindings=kb,
        multiline=True,
        prompt_continuation=_continuation,
        editing_mode=EditingMode.EMACS,
    )


def build_input_session() -> PromptSession:
    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        event.current_buffer.validate_and_handle()

    @kb.add("c-o")
    def _(event):
        event.current_buffer.insert_text("\n")

    @kb.add("escape", eager=True)
    def _(event):
        event.app.exit(result=S_CANCEL)

    return PromptSession(
        key_bindings=kb,
        multiline=True,
        prompt_continuation=_continuation,
        editing_mode=EditingMode.EMACS,
    )


def build_chat_session() -> PromptSession:
    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        event.current_buffer.validate_and_handle()

    @kb.add("c-o")
    def _(event):
        event.current_buffer.insert_text("\n")

    @kb.add("escape", eager=True)
    def _(event):
        event.app.exit(result=S_CANCEL)

    return PromptSession(
        key_bindings=kb,
        multiline=True,
        prompt_continuation=_continuation,
        editing_mode=EditingMode.EMACS,
    )


_MENU_SESSION: PromptSession | None = None
_INPUT_SESSION: PromptSession | None = None
_CHAT_SESSION: PromptSession | None = None


def _get(name, builder):
    global _MENU_SESSION, _INPUT_SESSION, _CHAT_SESSION
    if name == "menu":
        if _MENU_SESSION is None:
            _MENU_SESSION = builder()
        return _MENU_SESSION
    if name == "input":
        if _INPUT_SESSION is None:
            _INPUT_SESSION = builder()
        return _INPUT_SESSION
    if _CHAT_SESSION is None:
        _CHAT_SESSION = builder()
    return _CHAT_SESSION


def _label_to_formatted(label) -> FormattedText:
    if isinstance(label, FormattedText):
        return label
    if isinstance(label, str):
        return prompt_tag("prompt", label)
    return FormattedText([("", str(label))])


async def ask_menu(label=None) -> str:
    if label is None:
        label = prompt_tag("prompt", "> ")
    label = _label_to_formatted(label)
    return await _get("menu", build_menu_session).prompt_async(label)


async def ask_input(label=None) -> str:
    if label is None:
        label = prompt_tag("prompt", "> ")
    label = _label_to_formatted(label)
    return await _get("input", build_input_session).prompt_async(label)


async def ask_multiline(label=None) -> str:
    if label is None:
        label = prompt_tag("prompt", "Prompt: ")
    label = _label_to_formatted(label)
    session = _get("chat", build_chat_session)
    while True:
        text = await session.prompt_async(label)
        if text == S_CANCEL:
            raise KeyboardInterrupt
        if text.strip():
            return text