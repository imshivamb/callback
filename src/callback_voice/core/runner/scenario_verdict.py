from callback_voice.core.models.aggregate import Aggregate
from callback_voice.core.models.trial_result import TrialResult
from callback_voice.core.runner.trial_verdict import end_reason_failure
from callback_voice.scoring.aggregate.aggregate_spec import SPECS

_UNITS = {"s": " s", "ratio": "", "count": ""}
_THRESHOLDED_SOURCES = frozenset(s.source for s in SPECS if s.threshold is not None)


def scenario_verdict(
    trials: list[TrialResult], aggregates: list[Aggregate]
) -> tuple[bool, list[str]]:
    """A scenario passes when every thresholded aggregate passes.

    Thresholds apply across trials, so ``task_success_rate: 0.8`` lets one call in five
    fail its task. A failure no aggregate can express still fails the scenario: a
    metric that failed without a value (the agent never reprompted), a failed metric
    with no aggregate, and a call that dropped or ran out of time. Errored trials fail
    it too (and the run exits 2).
    """
    reasons = [_aggregate_reason(a) for a in aggregates if a.passed is False]
    for t in trials:
        if t.error is not None:
            reasons.append(f"trial {t.trial}: error: {t.error.splitlines()[0]}")
            continue
        for m in t.metrics:
            if m.method != "deterministic" or m.passed is not False:
                continue
            if m.value is None or m.name not in _THRESHOLDED_SOURCES:
                why = next((r for r in t.failure_reasons if r.startswith(m.name)), m.name)
                reasons.append(f"trial {t.trial}: {why}")
        if t.call is not None and (ended := end_reason_failure(t.call.end_reason)) is not None:
            reasons.append(f"trial {t.trial}: {ended}")
    return not reasons, reasons


def _aggregate_reason(a: Aggregate) -> str:
    """``task_success_rate 0.6 < 0.8 (95% CI 0.23–0.88, n=5)``."""
    unit = _UNITS.get(a.unit, "")
    op = ">" if a.comparator == "<=" else "<"
    ci = f"95% CI {a.ci_low:g}–{a.ci_high:g}, " if a.ci_low is not None else ""
    return f"{a.name} {a.value:g}{unit} {op} {a.threshold:g}{unit} ({ci}n={a.n})"
