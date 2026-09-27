"""The shared terminal console and its theme.

Colours mirror the design system: signal orange for the brand and failures that
matter, phosphor green for passes, muted graphite for secondary text.
"""

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

console = Console(theme=THEME, highlight=False)
err_console = Console(theme=THEME, stderr=True, highlight=False)
