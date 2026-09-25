from prompt_toolkit import PromptSession
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings

from . import config
from .themes import prompt_tag

S_QUIT     = "\x00QUIT"
S_CANCEL   = "\x00CANCEL"
S_RENAME   = "\x00RENAME"
S_DELETE   = "\x00DELETE"
S_EXPORT   = "\x00EXPORT"
S_SETTINGS = "\x00SETTINGS"
S_THEME    = "\x00THEME"
S_VERSION  = "\x00VERSION"
S_AUTOSEND = "\x00AUTOSEND"
S_BACK     = "\x00BACK"
S_NOTIFY   = "\x00NOTIFY"

_MENU_ACTIONS = [
    ("r", S_RENAME),
    ("d", S_DELETE),
    ("x", S_EXPORT),
    ("s", S_SETTINGS),
    ("q", S_QUIT),
]

_SETTINGS_ACTIONS = [
    ("a", S_AUTOSEND),
    ("t", S_THEME),
    ("v", S_VERSION),
    ("n", S_NOTIFY),
    ("b", S_BACK),
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


def _common_bindings(kb):
    @kb.add("enter")
    def _(event):
        event.current_buffer.validate_and_handle()

    @kb.add("c-o")
    def _(event):
        event.current_buffer.insert_text("\n")

    @kb.add("escape", eager=True)
    def _(event):
        # Save the draft before exiting on Esc
        text = event.current_buffer.text
        if text.strip():
            config.set_draft(text)
        event.app.exit(result=S_CANCEL)


def build_session(actions=None) -> PromptSession:
    kb = KeyBindings()
    _common_bindings(kb)
    if actions:
        for key, sentinel in actions:
            kb.add(key)(_action_handler(sentinel, key))
    return PromptSession(
        key_bindings=kb,
        multiline=True,
        prompt_continuation=_continuation,
        editing_mode=EditingMode.EMACS,
        enable_history_search=True,
        history=InMemoryHistory(),
    )


_MENU_SESSION: PromptSession | None = None
_INPUT_SESSION: PromptSession | None = None
_CHAT_SESSION: PromptSession | None = None
_SETTINGS_SESSION: PromptSession | None = None


def _get_menu() -> PromptSession:
    global _MENU_SESSION
    if _MENU_SESSION is None:
        _MENU_SESSION = build_session(_MENU_ACTIONS)
    return _MENU_SESSION


def _get_input() -> PromptSession:
    global _INPUT_SESSION
    if _INPUT_SESSION is None:
        _INPUT_SESSION = build_session()
    return _INPUT_SESSION


def _get_chat() -> PromptSession:
    global _CHAT_SESSION
    if _CHAT_SESSION is None:
        _CHAT_SESSION = build_session()
    return _CHAT_SESSION


def _get_settings() -> PromptSession:
    global _SETTINGS_SESSION
    if _SETTINGS_SESSION is None:
        _SETTINGS_SESSION = build_session(_SETTINGS_ACTIONS)
    return _SETTINGS_SESSION


def _label_to_formatted(label) -> FormattedText:
    if isinstance(label, FormattedText):
        return label
    if isinstance(label, str):
        return prompt_tag("prompt", label)
    return FormattedText([("", str(label))])


def _chat_prompt_label() -> FormattedText:
    """Build a prompt label that shows the active theme in dim brackets."""
    theme_name = config.get_theme_name()
    return FormattedText([
        ("#64c8ff", "Prompt: "),
        ("#787878", f"[{theme_name}] "),
    ])


async def ask_menu(label=None) -> str:
    if label is None:
        label = prompt_tag("prompt", "> ")
    return await _get_menu().prompt_async(_label_to_formatted(label))


async def ask_settings(label=None) -> str:
    if label is None:
        label = prompt_tag("prompt", "settings> ")
    return await _get_settings().prompt_async(_label_to_formatted(label))


async def ask_input(label=None) -> str:
    if label is None:
        label = prompt_tag("prompt", "> ")
    return await _get_input().prompt_async(_label_to_formatted(label))


async def ask_multiline(label=None) -> str:
    session = _get_chat()
    if label is None:
        label = _chat_prompt_label()
    else:
        label = _label_to_formatted(label)
    while True:
        text = await session.prompt_async(label)
        if text == S_CANCEL:
            raise KeyboardInterrupt
        if text.strip():
            return text