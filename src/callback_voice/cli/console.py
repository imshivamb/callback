"""The shared terminal console and its theme.

Colours mirror the design system: signal orange for the brand and failures that
matter, phosphor green for passes, muted graphite for secondary text.
"""

import io
import sys
from typing import TextIO

from rich.console import Console
from rich.theme import Theme

THEME = Theme(
    {
        "brand": "bold #ff5b1f",
        "pass": "bold #3ddc97",
        "fail": "bold #ff4d4f",
        "warn": "bold #ffb020",
        "skip": "#8a8f98",
        "muted": "#8a8f98",
        "caller": "#ffb37a",
        "agent": "#7cc4ff",
        "code": "#e6e6e6 on #1c1d21",
    }
)


def use_utf8(streams: tuple[TextIO, ...]) -> None:
    """Make Windows output streams UTF-8 so the ✓ ✕ ● marks can be written.

    Redirected output on Windows uses the ANSI code page (often cp1252), which cannot
    encode them: printing one raises UnicodeEncodeError. The interactive console is
    UTF-8 already (PEP 528) and is left alone.
    """
    if sys.platform != "win32":
        return
    for stream in streams:
        encoding = (stream.encoding or "").lower().replace("-", "").replace("_", "")
        if encoding != "utf8" and isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")


use_utf8((sys.stdout, sys.stderr))
console = Console(theme=THEME, highlight=False)
err_console = Console(theme=THEME, stderr=True, highlight=False)
