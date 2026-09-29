from rich.text import Text

from callback_voice.core.models.limit_override import LimitOverride

_WHAT = {"response_latency_p95_s": "reply delay p95", "chaos_drift_max_s": "chaos timing drift"}


def limit_notice(overrides: list[LimitOverride]) -> Text | None:
    """One warning line per loosened limit when this run uses CI limits."""
    if not overrides:
        return None
    lines: list[str] = []
    for metric in dict.fromkeys(o.metric for o in overrides):
        these = [o for o in overrides if o.metric == metric]
        applied = ", ".join(f"{a:g}" for a in sorted({o.applied for o in these}))
        target = ", ".join(f"{t:g}" for t in sorted({o.target for o in these}))
        lines.append(
            f"▲ CI limit: {_WHAT.get(metric, metric)} up to {applied} s on this machine "
            f"({these[0].source}); the real target is {target} s."
        )
    return Text("\n".join(lines) + "\n", style="warn")
