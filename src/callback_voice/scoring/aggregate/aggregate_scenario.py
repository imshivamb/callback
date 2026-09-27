from collections.abc import Callable

import numpy as np

from callback_voice.core.models.aggregate import Aggregate
from callback_voice.core.models.metric import judge_threshold
from callback_voice.core.models.thresholds import Thresholds
from callback_voice.core.models.trial_result import TrialResult
from callback_voice.core.seeds.derive_seed import derive_seed
from callback_voice.scoring.aggregate.aggregate_spec import SPECS, AggregateSpec
from callback_voice.scoring.stats.bootstrap import bootstrap_interval
from callback_voice.scoring.stats.wilson import wilson_interval


def aggregate_scenario(
    trials: list[TrialResult], thresholds: Thresholds, seed: int
) -> list[Aggregate]:
    """Every scenario-level number with its 95% interval and verdict.

    Errored trials are left out (the run already exits 2). Metrics no trial produced
    are omitted rather than reported as zero.
    """
    scored = [t for t in trials if t.error is None]
    out = [a for spec in SPECS if (a := _aggregate(spec, scored, thresholds, seed)) is not None]
    return out


def _aggregate(
    spec: AggregateSpec, trials: list[TrialResult], thresholds: Thresholds, seed: int
) -> Aggregate | None:
    threshold = spec.threshold(thresholds) if spec.threshold else None
    if spec.name == "call_pass_rate":
        passes = [t.passed for t in trials]
    else:
        metrics = [
            m for t in trials if (m := t.metric(spec.source)) is not None and m.value is not None
        ]
        if not metrics:
            return None
    value: float | None
    interval: tuple[float, float] | None
    match spec.reducer:
        case "rate":
            if spec.name != "call_pass_rate":
                passes = [bool(m.passed) for m in metrics]
            if not passes:
                return None
            value = sum(passes) / len(passes)
            interval = wilson_interval(sum(passes), len(passes))
            n = len(passes)
        case "pooled_p95" | "pooled_p50":
            q = 95 if spec.reducer == "pooled_p95" else 50
            per_call = [m.samples for m in metrics if m.samples]
            pooled = [s for call in per_call for s in call]
            if not pooled:
                return None
            value = float(np.percentile(pooled, q))
            interval = bootstrap_interval(per_call, _percentile(q), derive_seed(seed, spec.name))
            n = len(pooled)
        case "mean" | "max":
            values = [float(m.value) for m in metrics if m.value is not None]
            value = float(np.mean(values)) if spec.reducer == "mean" else max(values)
            interval = (min(values), max(values)) if len(values) > 1 else None
            if spec.reducer == "mean" and len(values) > 1:
                interval = bootstrap_interval(
                    [[v] for v in values], lambda a: float(np.mean(a)), derive_seed(seed, spec.name)
                )
            n = len(values)
    return Aggregate(
        name=spec.name,
        value=round(value, 4),
        n=n,
        unit=spec.unit,
        method="deterministic",
        ci_low=None if interval is None else round(interval[0], 4),
        ci_high=None if interval is None else round(interval[1], 4),
        threshold=threshold,
        comparator=spec.comparator,
        passed=None if threshold is None else judge_threshold(value, threshold, spec.comparator),
    )


def _percentile(q: int) -> Callable[[np.ndarray], float]:
    """The q-th percentile as a function, for bootstrap resampling."""

    def statistic(values: np.ndarray) -> float:
        return float(np.percentile(values, q))

    return statistic
