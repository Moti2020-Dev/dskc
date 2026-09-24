# DSKC — DeepSeek Client

A terminal client for DeepSeek's web chat. Talks to the same backend the browser uses, so it's free, requires no API key, and supports the same models and features. Renders markdown and true 24-bit color, persists chats locally, and lets you resume any conversation across restarts.

```
 ▛▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
 ▌  ◆  D S K C  ·  D E E P S E E K          ▐
 ▌     a command-line client                ▐
 ▙▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
```

---

## Features

### Core

- **Free to use** — no subscription, no per-token billing, hits the web endpoint directly
- **No API key** — uses your browser's `userToken` from Local Storage
- **Streaming responses** — reads the SSE stream from `/api/v0/chat/completion`
- **Multi-turn conversations** — threads via `parent_message_id` so replies append properly
- **PoW challenge solving** — solves `DeepSeekHashV1` via a WASM solver in milliseconds
- **Session persistence** — chats, titles, and parent IDs saved in `chats.json`

### Chat management

- **New chats** created server-side via `/api/v0/chat_session/create`
- **Resume by number** — pick from the menu
- **Resume by UUID** — paste a full chat ID
- **Rename** and **delete** from the menu
- **Auto-titling** — the model prepends `\{Title}\`; the client strips and saves it
- **Server title fallback** — fetches the title from the server if the model doesn't send one

### Chat features

- **Browser link** — OSC-8 hyperlink to `chat.deepseek.com/a/chat/s/{uuid}` above the prompt
- **Per-chat history** — every message appended to `history/{uuid}.json`
- **Markdown export** — writes `export_{uuid}.md` with full transcript
- **Autosend** — a message sent automatically at the start of every new chat; useful for teaching the model a style guide

### Rendering

- **Full markdown** — headers (with underline rules), bold, italic, strikethrough, inline code, fenced code blocks, bullet lists, ordered lists, blockquotes, links, horizontal rules
- **True 24-bit color** — `\033[38;2;R;G;Bm` / `\033[48;2;R;G;Bm`
- **Automatic 256-color fallback** — uses `\033[38;5;Nm` when `COLORTERM` isn't `truecolor`
- **Custom color syntax** the model can use in replies:
  - `\C:{preset}text` — foreground preset
  - `\B:{preset}text` — background preset
  - `\Cx{RRGGBB}text` — foreground hex
  - `\Bx{RRGGBB}text` — background hex
  - `\U:on` / `\U:off` — underline
  - `\R` — reset
- **Auto reset at newlines** — no need to close spans
- **Named presets** — `black`, `red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, `white`, `gray`, plus 16 ANSI variants

### Theming

- **`themes.json`** — every UI color as a named tag; edit the file to add new themes
- **Semantic tags** — `banner`, `prompt`, `error`, `success`, `dim`, `chat_num`, `link`, etc.
- **Built-in themes** — `default`, `dracula`, `nord`
- **Live switching** — `s` → `t` picks a theme
- **Fallback chain** — missing theme → `default` → built-in → no color

### UI / UX

- **Gradient banner** with dark-blue → cyan eight-stop ramp
- **Configurable version** shown in the banner
- **Single-key menu actions** — `r` rename, `d` delete, `x` export, `s` settings, `q` quit
- **Settings submenu** — autosend, theme, version under `s`
- **Context-aware keys** — single-key actions only fire on an empty buffer; typed text is unaffected
- **Multiline input** — `Enter` submits, `Ctrl+O` inserts a newline, `Esc` cancels
- **Ctrl+C / Ctrl+D** — `Ctrl+C` returns to the menu, `Ctrl+D` exits
- **Keywords** — `stop`, `quit`, `exit`, `:export`

### Diagnostics

- **`--debug`** — verbose output throughout
- **SSE tracing** — every event and data line
- **PoW timing** — difficulty and elapsed milliseconds
- **Stream stats** — chunks, characters, elapsed time, response ID
- **Escape tracing** — every preset/hex lookup; unknown presets flagged
- **One-shot dedup** — `dbg(..., once=True)` avoids repeated lines

### Developer

- **Modular layout** — `dskc/` with one file per concern
- **`--test`** — renders a markdown sample and exits
- **Local storage** — all data next to `main.py`
- **No global state** — sessions and caches live in well-defined modules

---

## Requirements

- Python 3.10 or newer
- A C++17 compiler only if you install `aiodeepseek` (not required for the WASM path)
- A terminal with 256-color or truecolor support (Konsole, GNOME Terminal, iTerm2, Kitty, WezTerm, Windows Terminal all work)

## Installation

```bash
git clone <your-repo-url> ~/code/AI
cd ~/code/AI
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Setup

### 1. Get the WASM PoW solver

Download `sha3_wasm_bg.7b9ca65ddd.wasm` and place it at:

```
~/code/AI/wasm/sha3_wasm_bg.7b9ca65ddd.wasm
```

Sources: [dskpp](https://github.com/Fundiman/dskpp), [Chat2API](https://github.com/lz-star/deepseek-free-api), or extract it from the DeepSeek frontend bundle.

### 2. Get your `userToken`

1. Log in to [chat.deepseek.com](https://chat.deepseek.com)
2. Open DevTools (F12) → **Application** → **Local Storage** → `https://chat.deepseek.com`
3. Copy the value of the key `userToken`

Or from the browser **Console**:

```javascript
JSON.parse(localStorage.getItem("userToken")).value
```

### 3. Create `.env`

```
DEEPSEEK_TOKEN=your_copied_userToken_here
```

### 4. Verify

```bash
python3 -c "from dskc.config import get_token; print('token:', get_token() is not None)"
```

Should print `token: True`.

---

## Usage

```bash
python3 main.py
```

You'll see the menu:

```
 ▛▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
 ▌  ◆  D S K C  ·  D E E P S E E K          ▐
 ▌     a command-line client                ▐
 ▙▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄

  V1.7  [default]
  ──────────────────────────────────────────────
    1.  My First Chat  [88bab68d]
    2.  Debugging Session  [f51ae83f]

 0.  New chat
  autosend: Format replies with these codes...
  r rename   d delete   x export   s settings   q quit

>
```

### Menu keys

| Key | Action |
|---|---|
| `1`–`9` + Enter | Open that chat |
| `0` + Enter | Create a new chat |
| `r` | Rename a chat |
| `d` | Delete a chat |
| `x` | Export a chat to markdown |
| `s` | Open settings |
| `q` | Quit |

### Settings

| Key | Action |
|---|---|
| `a` | Edit the autosend message |
| `t` | Pick a theme |
| `v` | Change the version string |
| `b` | Back to the main menu |

### Chat prompt

| Input | Action |
|---|---|
| Text + Enter | Send message |
| `Ctrl+O` | Insert a newline |
| `Esc` | Cancel, back to menu |
| `Ctrl+C` | Back to menu |
| `Ctrl+D` | Quit the program |
| `stop` | Quit the program |
| `quit` / `exit` | Back to menu |
| `:export` | Export the current chat |

### Flags

```bash
python3 main.py --debug    # verbose output
python3 main.py --test     # render a markdown sample and exit
```

---

## Teaching the model the color syntax

DeepSeek doesn't emit `\C:{cyan}` or `\Cx{FF5733}` on its own. You have to tell it to. The **autosend** feature handles this: configure a message once and it's sent automatically at the start of every new chat.

Suggested autosend message:

```
You are replying to a terminal client that renders ANSI colors and basic markdown.

Markdown is rendered: # headers, **bold**, *italic*, ~~strikethrough~~, `code`, ``` fenced blocks ```, - lists, > quotes, [links](url).

You can also color text with these codes:
  \C:{preset}text     foreground preset
  \B:{preset}text     background preset
  \Cx{RRGGBB}text     foreground hex
  \Bx{RRGGBB}text     background hex
  \U:on / \U:off      underline
  \R                  reset

Braces go around the preset name or hex value ONLY, never around the text.
A reset is applied automatically at every newline, so no closing code is needed.
No nesting. No color codes inside code fences.

Presets: black, red, green, yellow, blue, magenta, cyan, white, gray, plus ansi_* and ansi_bright_* variants.

Use color tastefully — headings, warnings, emphasis, status. Not every word.

Confirm and wait for my next message.
```

Set it via `s` → `a` in the menu.

---

## Project layout

```
~/code/AI/
├── main.py                    # entry point
├── dskc/
│   ├── __init__.py            # DEFAULT_VERSION
│   ├── paths.py               # all file paths
│   ├── config.py              # config.json, themes.json
│   ├── themes.py              # tag, prompt_tag, theme helpers
│   ├── colors.py              # custom escape parser + markdown render
│   ├── storage.py             # chats, per-chat history
│   ├── export.py              # markdown export
│   ├── api.py                 # DeepSeek API calls, PoW, SSE
│   ├── banner.py              # gradient banner
│   ├── sessions.py            # prompt_toolkit sessions + ask helpers
│   ├── settings.py            # settings submenu
│   ├── menu.py                # main menu
│   └── chat.py                # chat loop
├── lib_color.py               # ANSI color + markdown library
├── pow_solver.py              # WASM PoW wrapper
├── wasm/
│   └── sha3_wasm_bg.7b9ca65ddd.wasm
├── requirements.txt
├── .env                       # DEEPSEEK_TOKEN (gitignored)
├── config.json                # autosend, version, theme (gitignored)
├── themes.json                # theme definitions
├── chats.json                 # chat list (gitignored)
├── history/                   # per-chat message logs (gitignored)
└── export_*.md                # exported chats (gitignored)
```

---

## Custom color syntax reference

The client parses these escapes in the model's replies and in anything you type:

| Syntax | Meaning |
|---|---|
| `\C:{preset}text` | Foreground preset |
| `\B:{preset}text` | Background preset |
| `\Cx{RRGGBB}text` | Foreground hex |
| `\Bx{RRGGBB}text` | Background hex |
| `\U:on` | Start underline |
| `\U:off` | End underline |
| `\R` | Reset all attributes |

Each color escape runs from where it appears to the next escape or end of line. A reset is applied automatically at every newline.

### Presets

**24-bit named:**

```
black, red, green, yellow, blue, magenta, cyan, white, gray
```

**16 ANSI:**

```
ansi_black, ansi_red, ansi_green, ansi_yellow,
ansi_blue, ansi_magenta, ansi_cyan, ansi_white,
ansi_bright_black, ansi_bright_red, ansi_bright_green,
ansi_bright_yellow, ansi_bright_blue, ansi_bright_magenta,
ansi_bright_cyan, ansi_bright_white
```

Preset names are case-insensitive. Hex digits are case-insensitive.

### Examples

```
\C:{cyan}This whole line is cyan.
\C:{red}Red text \C:{yellow}then yellow \C:{green}then green.
\Cx{FF5733}Orange from hex.
\B:{blue}Blue background for this line.
\Bx{330033}\Cx{00FFCC}Teal on dark purple.
\U:onUnderlined text\U:off back to normal.
```

---

## Theming

Create `themes.json` next to `main.py`. Each theme is a flat dictionary of semantic tags to `"R,G,B"` strings.

```json
{
  "default": {
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
    "link": "100,200,255"
  },
  "dracula": {
    "banner": "189,147,249",
    "version": "241,250,140",
    "prompt": "139,233,253",
    "success": "80,250,123",
    "error": "255,85,85",
    "chat_num": "255,184,108"
  }
}
```

Any tag you omit falls back to the `default` theme's value, and then to a built-in default. Add as many themes as you want. Switch with `s` → `t`.

---

## Configuration files

| File | Purpose | Committed? |
|---|---|---|
| `.env` | `DEEPSEEK_TOKEN` | No |
| `config.json` | Autosend, version, theme | No |
| `chats.json` | Chat list, titles, parent IDs | No |
| `history/*.json` | Per-chat message logs | No |
| `themes.json` | Theme definitions | Yes |
| `export_*.md` | Exported chats | No |

---

## Troubleshooting

### `ModuleNotFoundError` or `NameError`

Run this from the project root:

```bash
python3 -c "import dskc.config, dskc.themes, dskc.colors, dskc.storage, dskc.api, dskc.sessions, dskc.settings, dskc.menu, dskc.chat, dskc.banner, dskc.export; print('all ok')"
```

If it fails, the traceback names the exact file and symbol. For static checks, install [ruff](https://docs.astral.sh/ruff/) and run `ruff check dskc/`.

### Colors aren't rendering

Test the terminal:

```bash
printf '\033[38;2;255;215;0mGOLD\033[0m\n'
printf '\033[38;5;214mGOLD-256\033[0m\n'
```

If neither renders, your terminal doesn't support ANSI colors, or `NO_COLOR` is set. Unset it:

```bash
unset NO_COLOR
echo $COLORTERM   # should be "truecolor" for full RGB
```

To force 24-bit color in Konsole and similar:

```bash
export COLORTERM=truecolor
```

Add to `~/.bashrc` to make it permanent.

### PoW failure

If `PoW not solved` appears, the WASM file may be missing or corrupt. Verify:

```bash
ls -la wasm/sha3_wasm_bg.7b9ca65ddd.wasm
```

Re-download from the sources above if needed.

### `invalid chat session id`

Your `userToken` has expired or been invalidated. Re-extract it from Local Storage and update `.env`.

### `Ctrl+D` quits instead of `Ctrl+C`

That's by design: `Ctrl+C` cancels the current action and returns to the menu; `Ctrl+D` exits the program. If you want different semantics, edit the `except` clauses in `dskc/sessions.py`.

### The AI's replies have escape codes in them, but they show as literal text

The model is emitting codes the parser doesn't recognize. Run with `--debug` and look for lines like `[DEBUG] preset fg unknown = <name>`. The autosend message might need updating, or the model drifted. Re-send the style guide mid-chat.

---

## Security notes

- The `userToken` is a **session credential**. Anyone who has it can access your DeepSeek account until it expires. Keep `.env` out of version control.
- The `userToken` does not expire on logout — it persists until explicitly revoked. Rotate by logging out and back in if you suspect it leaked.
- `.gitignore` excludes `.env`, `config.json`, `chats.json`, `history/`, and `export_*.md` by default.

---

## Limitations

- **Uses an undocumented internal API.** DeepSeek may change it without notice. If the client breaks, check the endpoints in `dskc/api.py`.
- **Not a replacement for the official API.** If you want a stable, supported interface with an API key, use [api.deepseek.com](https://api.deepseek.com).
- **Nested color spans are not supported.** Each `\C:` / `\B:` runs to the next escape or end of line.
- **No streaming display.** Replies are printed in full once the stream completes. Adding live streaming would require a state machine for markdown and custom escapes.
- **No file uploads.** The client doesn't handle `ref_file_ids`.

---

## Contributing

The `dskc/` package is organized so each module has a single responsibility. When adding a feature:

| Feature type | Touch these files |
|---|---|
| New color escape | `dskc/colors.py` |
| New theme tag | `dskc/themes.py`, `themes.json` |
| New menu action | `dskc/sessions.py` (sentinel + binding), `dskc/menu.py` (dispatch) |
| New setting | `dskc/config.py` (getter/setter), `dskc/settings.py` (UI) |
| New API endpoint | `dskc/api.py` |
| New export format | `dskc/export.py`, `dskc/menu.py` (branch) |

---

## License

MIT

---

## Acknowledgments

- [DeepSeek](https://deepseek.com) for the model
- [dskpp](https://github.com/Fundiman/dskpp) and [Chat2API](https://github.com/lz-star/deepseek-free-api) for reverse-engineering references
- [prompt_toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit) for the input layer
- [wasmtime](https://wasmtime.dev) for the WASM runtime