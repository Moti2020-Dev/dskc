# 
 
 A terminal-based chat client for DeepSeek, with a custom inline
 color markup language for styled output.

 
 ## Features
 
 - Chat with DeepSeek from your terminal
 - Custom escape codes for foreground/background color
   (presets, hex, nesting, reset)
 - Markdown rendering inline (bold, italic, strikethrough, code)
 - Export chats to JSON (raw, lossless) or HTML (styled)
 - Recent chat history, debug mode, test mode
 
 ## Requirements
 
 - Python 3.10+
 - A terminal with truecolor support (most modern emulators)
 - A DeepSeek API key
 
 ## Install
 
     pip install -r requirements.txt
 
 ## Configure
 
 Set your API key:
 
     export DEEPSEEK_API_KEY="sk-..."
 
 (or copy `.env.example` to `.env` and fill it in)
 
 ## Run
 
     python3 main.py
 
 Flags:
 - `--debug`  verbose logging
 - `--test`   run with a mock backend
 
 On first launch, create a chat if you don't have one in recent history.
 
 ## Color Codes
 
 | Code           | Meaning                    |
 |----------------|----------------------------|
 | ``  | foreground, named preset   |
 | ``  | background, named preset   |
 | `\Cx{RRGGBB}`  | foreground, hex            |
 | `\Bx{RRGGBB}`  | background, hex            |
 | ``           | reset fg and bg            |
 
 Presets: `black, red, green, yellow, blue, magenta, cyan, white, gray`
 
 ## License
 
 MIT