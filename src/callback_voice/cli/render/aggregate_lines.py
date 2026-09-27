from rich.console import Group, RenderableType
from rich.text import Text

from callback_voice.core.models.aggregate import Aggregate
from callback_voice.core.models.baseline_diff import BaselineDiff
from callback_voice.core.models.scenario_result import ScenarioResult

_UNITS = {"s": " s", "ratio": "", "count": ""}


def aggregate_lines(scenario: ScenarioResult, diffs: list[BaselineDiff]) -> RenderableType:
    """A scenario's verdict, then one line per aggregate: value, 95% interval, limit,
    and how it moved against the baseline."""
    regressed = any(d.regressed for d in diffs)
    mark, style = ("●", "pass") if scenario.passed and not regressed else ("✕", "fail")
    n = len(scenario.trials)
    lines: list[RenderableType] = [
        Text.assemble(
            (f"  {mark} ", style),
            (scenario.scenario_id, "bold"),
            (f"  {n} trial(s)", "muted"),
            ("  regressed vs baseline" if regressed else "", "fail"),
        )
    ]
    by_metric = {d.metric: d for d in diffs}
    width = max((len(a.name) for a in scenario.aggregates), default=0)
    for a in scenario.aggregates:
        lines.append(_line(a, by_metric.get(a.name), width))
    lines += [Text(f"      {reason}", style="fail") for reason in scenario.failure_reasons]
    return Group(*lines)


def _line(a: Aggregate, diff: BaselineDiff | None, width: int) -> Text:
    unit = _UNITS.get(a.unit, "")
    text = Text(f"      {a.name:<{width}}  ", style="muted")
    text.append(f"{a.value:.3g}{unit}", style="bold")
    if a.ci_low is not None and a.ci_high is not None:
        text.append(f"  [{a.ci_low:.3g}–{a.ci_high:.3g}]", style="muted")
    if a.threshold is not None:
        ok = "✓" if a.passed else "✕"
        text.append(f"  {a.comparator} {a.threshold:g}{unit} {ok}", "pass" if a.passed else "fail")
    if diff is not None and diff.delta is not None and diff.baseline is not None:
        text.append("  " + _moved(diff, unit), _moved_style(diff))
    return text


def _moved(d: BaselineDiff, unit: str) -> str:
    assert d.delta is not None and d.baseline is not None
    arrow = "=" if d.direction == "same" else "↑" if d.delta > 0 else "↓"
    said = {
        "same": "same",
        "better": "better",
        "worse": "REGRESSED" if d.regressed else "worse, within noise",
    }.get(d.direction, d.direction)
    return f"{arrow} {d.delta:+.3g}{unit} vs {d.baseline:.3g}{unit} ({said})"


def _moved_style(d: BaselineDiff) -> str:
    if d.regressed:
        return "fail"
    return "pass" if d.direction == "better" else "muted"
