from itertools import groupby

from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text

from callback_voice.doctor.check_result import CheckResult

_MARKS = {"ok": ("●", "pass"), "warn": ("▲", "warn"), "fail": ("✕", "fail"), "skip": ("○", "skip")}


def check_table(results: list[CheckResult]) -> RenderableType:
    """Doctor results grouped by area, each with a status mark and an optional fix line."""
    sections: list[RenderableType] = []
    for group, items in groupby(results, key=lambda r: r.group):
        table = Table.grid(padding=(0, 2))
        table.add_column(width=1)
        table.add_column(min_width=18, style="bold")
        table.add_column()
        for result in items:
            mark, style = _MARKS[result.status]
            detail = Text(result.detail, style="muted" if result.status == "skip" else "")
            if result.fix:
                detail.append(f"\n→ {result.fix}", style="brand")
            table.add_row(Text(mark, style=style), result.name, detail)
        sections.append(Group(Text(group.upper(), style="muted"), table, Text()))
    return Group(*sections)
