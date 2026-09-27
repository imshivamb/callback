from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric

_UNITS = {"s": " s", "ratio": "", "count": ""}
_FAILING_ENDS = {"max_duration": "the call hit max_duration_s without finishing"}


def trial_verdict(
    metrics: list[Metric], findings: list[Finding], end_reason: str
) -> tuple[bool, list[str]]:
    """A trial passes when no deterministic metric fails and the call ended normally.

    Every failed metric yields a reason: its value against the threshold, or, when
    there is no value (the agent never reprompted), the metric's first finding.
    Judged metrics inform but never fail a trial by default.
    """
    reasons: list[str] = []
    for m in metrics:
        if m.method != "deterministic" or m.passed is not False:
            continue
        if m.value is not None and m.threshold is not None:
            op = ">" if m.comparator == "<=" else "<"
            unit = _UNITS.get(m.unit, "")
            reasons.append(f"{m.name} {m.value:g}{unit} {op} {m.threshold:g}{unit}")
        else:
            first = next((f.message for f in findings if m.name.startswith(f.metric)), "failed")
            reasons.append(f"{m.name}: {first}")
    if end_reason in _FAILING_ENDS:
        reasons.append(_FAILING_ENDS[end_reason])
    if end_reason.startswith("connection_lost"):
        reasons.append(f"the call dropped: {end_reason}")
    return not reasons, reasons
