from collections.abc import Mapping

from callback_voice.core.models.aggregate import Aggregate
from callback_voice.core.models.baseline import Baseline
from callback_voice.core.models.baseline_diff import BaselineDiff
from callback_voice.core.models.scenario_result import ScenarioResult

_SAME = 1e-9


def compare_to_baseline(
    scenarios: list[ScenarioResult], baseline: Baseline, min_effect: Mapping[str, float]
) -> list[BaselineDiff]:
    """Every aggregate of every scenario the baseline also has, against its old value.

    A move is a regression only when it is worse, beyond noise (the 95% intervals do
    not overlap; a missing interval cannot show overlap) and at least ``min_effect``.
    Scenarios the baseline never ran are skipped.
    """
    diffs: list[BaselineDiff] = []
    for scenario in scenarios:
        old = baseline.scenarios.get(scenario.scenario_id)
        if old is None:
            continue
        before = {a.name: a for a in old}
        now = {a.name: a for a in scenario.aggregates}
        for name in [*now, *(n for n in before if n not in now)]:
            diffs.append(
                _diff(scenario.scenario_id, name, before.get(name), now.get(name), min_effect)
            )
    return diffs


def _diff(
    scenario_id: str,
    name: str,
    before: Aggregate | None,
    now: Aggregate | None,
    min_effect: Mapping[str, float],
) -> BaselineDiff:
    effect = min_effect.get(name, 0.0)
    base = BaselineDiff(
        scenario_id=scenario_id,
        metric=name,
        baseline=before.value if before else None,
        current=now.value if now else None,
        delta=None,
        baseline_ci=_ci(before),
        current_ci=_ci(now),
        min_effect=effect,
        direction="new" if before is None else "missing",
        regressed=False,
    )
    if before is None or now is None or before.value is None or now.value is None:
        return base
    delta = now.value - before.value
    lower_is_better = now.comparator == "<="
    if abs(delta) <= _SAME:
        direction = "same"
    elif (delta > 0) == lower_is_better:
        direction = "worse"
    else:
        direction = "better"
    old_ci, new_ci = base.baseline_ci, base.current_ci
    if old_ci is None or new_ci is None:
        separated = True
    elif lower_is_better:
        separated = new_ci[0] > old_ci[1]
    else:
        separated = new_ci[1] < old_ci[0]
    regressed = direction == "worse" and separated and abs(delta) >= effect - _SAME
    return base.model_copy(
        update={"delta": round(delta, 4), "direction": direction, "regressed": regressed}
    )


def _ci(a: Aggregate | None) -> tuple[float, float] | None:
    if a is None or a.ci_low is None or a.ci_high is None:
        return None
    return a.ci_low, a.ci_high
