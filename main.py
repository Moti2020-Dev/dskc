#!/usr/bin/env python3
import asyncio
import sys
from dskc import config
from dskc.menu import run as run_menu


async def main():
    token = config.get_token()
    if not token:
        raise ValueError("DEEPSEEK_TOKEN not set in .env")
    await run_menu(token)


if __name__ == "__main__":
    if "--test" in sys.argv:
        from dskc.colors import render_markdown
        sample = (
            "# Heading 1\n"
            "## Heading 2\n\n"
            "Plain **bold** and *italic* and `code`.\n\n"
            "\\C:{cyan}cyan preset \\U:onand underlined\\U:off\n"
            "\\C:{red}red preset \\C:{yellow}then yellow\n"
            "\\Cx{FF5733}orange hex\n"
            "\\B:{blue}blue background\n"
            "\\Bx{330033}and a purple background\n"
            "~~strikethrough~~ and \\U:onunderlined text\\U:off\n"
        )
        print(render_markdown(sample))
        sys.exit(0)

    try:
        asyncio.run(main())
    except SystemExit:
        pass
    except (KeyboardInterrupt, EOFError):
        pass