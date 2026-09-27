from callback_voice.core.models.metric import Metric

_UNITS = {"s": " s", "ratio": "", "count": ""}
_FAILING_ENDS = {"max_duration": "the call hit max_duration_s without finishing"}


def trial_verdict(metrics: list[Metric], end_reason: str) -> tuple[bool, list[str]]:
    """A trial passes when no deterministic metric fails and the call ended normally.

    Judged metrics inform but never fail a trial by default.
    """
    reasons = [
        f"{m.name} {m.value:g}{_UNITS.get(m.unit, '')} {'>' if m.comparator == '<=' else '<'} "
        f"{m.threshold:g}{_UNITS.get(m.unit, '')}"
        for m in metrics
        if m.method == "deterministic"
        and m.passed is False
        and m.value is not None
        and m.threshold is not None
    ]
    if end_reason in _FAILING_ENDS:
        reasons.append(_FAILING_ENDS[end_reason])
    if end_reason.startswith("connection_lost"):
        reasons.append(f"the call dropped: {end_reason}")
    return not reasons, reasons
