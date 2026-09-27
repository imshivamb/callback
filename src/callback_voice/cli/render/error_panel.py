from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from callback_voice.errors import CallbackError


def error_panel(error: CallbackError) -> RenderableType:
    """A framed error with an optional one-line fix, for exit-code-2 failures."""
    body: list[RenderableType] = [Text(str(error))]
    if error.hint:
        body.append(Text.assemble(("\nfix  ", "muted"), (error.hint, "bold")))
    return Panel(
        Group(*body),
        title=Text(f" {type(error).__name__} ", style="fail"),
        title_align="left",
        border_style="#ff4d4f",
        padding=(1, 2),
    )
