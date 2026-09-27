from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric

_UNITS = {"s": " s", "ratio": "", "count": ""}
_EXPLAINED = frozenset({"task_success", "entity_fidelity", "policy_violations"})
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
            reason = f"{m.name} {m.value:g}{unit} {op} {m.threshold:g}{unit}"
            if m.name in _EXPLAINED:  # a bare number says nothing about what went wrong
                why = next(
                    (f.message for f in findings if f.metric == m.name and f.severity == "fail"),
                    None,
                )
                reason += f": {why}" if why else ""
            reasons.append(reason)
        else:
            first = next((f.message for f in findings if m.name.startswith(f.metric)), "failed")
            reasons.append(f"{m.name}: {first}")
    if (ended_badly := end_reason_failure(end_reason)) is not None:
        reasons.append(ended_badly)
    return not reasons, reasons


def end_reason_failure(end_reason: str) -> str | None:
    """Why the way a call ended is itself a failure, or None if it ended normally."""
    if end_reason in _FAILING_ENDS:
        return _FAILING_ENDS[end_reason]
    if end_reason.startswith("connection_lost"):
        return f"the call dropped: {end_reason}"
    return None
