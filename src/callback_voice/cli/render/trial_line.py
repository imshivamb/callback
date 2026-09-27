from rich.console import Group, RenderableType
from rich.text import Text

from callback_voice.core.models.trial_result import TrialResult


def trial_line(result: TrialResult, trials: int) -> RenderableType:
    """One line per finished call: verdict, key numbers, and why it failed."""
    if result.error:
        head = Text.assemble(
            ("  ✕ ", "fail"),
            (result.scenario_id, "bold"),
            (f"  trial {result.trial}/{trials}  ", "muted"),
            ("error", "fail"),
        )
        return Group(head, Text(f"      {result.error.splitlines()[0]}", style="fail"))
    mark, style = ("●", "pass") if result.passed else ("✕", "fail")
    latency = result.metric("response_latency_p95_s")
    duration = result.call.duration_s if result.call else 0.0
    facts = [
        f"latency p95 {latency.value:.2f} s"
        if latency and latency.value is not None
        else "no answered turns",
        f"{duration:.0f} s call",
        result.call.end_reason if result.call else "",
    ]
    lines: list[RenderableType] = [
        Text.assemble(
            (f"  {mark} ", style),
            (result.scenario_id, "bold"),
            (f"  trial {result.trial}/{trials}  ", "muted"),
            (" · ".join(f for f in facts if f), "muted"),
        )
    ]
    lines += [Text(f"      {reason}", style="fail") for reason in result.failure_reasons]
    if result.review:
        checks = ", ".join(item.check for item in result.review)
        lines.append(
            Text(
                f"      ▲ {len(result.review)} check(s) need a person to listen: {checks}",
                style="warn",
            )
        )
    return Group(*lines)
