"""The report's plain-language layer: one sentence and a few problem tiles.

Built from the numbers alone (no LLM), so the same results always read the same way.
"""

from dataclasses import dataclass
from typing import Any

from callback_voice.core.models.aggregate import Aggregate
from callback_voice.core.models.baseline_diff import BaselineDiff
from callback_voice.core.models.run_result import RunResult
from callback_voice.core.models.scenario_result import ScenarioResult
from callback_voice.core.models.trial_result import TrialResult
from callback_voice.scoring.aggregate.aggregate_spec import SPECS


@dataclass(frozen=True, slots=True)
class _Kind:
    finding: str  # the per-call finding metric that locates it
    title: str  # tile title
    phrase: str  # "the agent ..." phrase; {v} and {limit} are formatted values
    weight: float  # lower is more serious; decides order


_KINDS: dict[str, _Kind] = {
    "task_success_rate": _Kind(
        "task_success", "Doesn't finish the task", "doesn't finish the task ({v} of calls)", 0
    ),
    "entity_fidelity": _Kind(
        "entity_fidelity", "Gets facts wrong", "gets facts wrong when reading them back", 1
    ),
    "policy_violations": _Kind(
        "policy_violations", "Says what it must not", "says something it must not", 2
    ),
    "unanswered_turns": _Kind(
        "unanswered_turns",
        "Ignores the caller",
        "doesn't answer the caller at all ({v} times in a call)",
        2.7,
    ),
    "time_to_yield_p95_s": _Kind(
        "time_to_yield",
        "Talks over interruptions",
        "keeps talking when the caller interrupts ({v} vs {limit})",
        3,
    ),
    "false_yields": _Kind(
        "false_yield",
        "Stops for “mm-hmm”",
        "stops talking when the caller only says “mm-hmm” ({v} times in a call)",
        4,
    ),
    "silence_reprompt_s": _Kind(
        "silence_reprompt",
        "Slow to check on silence",
        "takes too long to check in when the caller goes quiet ({v} vs {limit})",
        5,
    ),
    "talk_over_ratio": _Kind(
        "talk_over", "Talks over the caller", "talks over the caller ({v} of their speech)", 6
    ),
    "response_latency_p95_s": _Kind(
        "response_latency",
        "Replies too slowly",
        "replies too slowly ({v} vs a {limit} limit)",
        7,
    ),
}

# Neutral names for a number that moved, whether or not it is over its limit.
_NAMES = {
    "response_latency_p95_s": "reply delay",
    "response_latency_p50_s": "typical reply delay",
    "time_to_yield_p95_s": "time to stop when interrupted",
    "talk_over_ratio": "talk-over",
    "false_yields": "stops for “mm-hmm”",
    "silence_reprompt_s": "time to check on silence",
    "task_success_rate": "task success",
    "entity_fidelity": "facts correct",
    "policy_violations": "policy violations",
    "unanswered_turns": "unanswered turns",
    "call_pass_rate": "calls passed",
}

# Failures no across-call number carries, recognised in a scenario's reasons.
_STRUCTURAL = (
    ("silence_reprompt", "never checks in when the caller goes quiet"),
    ("the call dropped", "drops the call"),
    ("max_duration", "runs out of time before the call finishes"),
)


def summarize_run(result: RunResult) -> dict[str, Any]:
    """The run's one sentence and up to three problem tiles, most serious first."""
    errored = [t for s in result.scenarios for t in s.trials if t.error]
    calls = sum(len(s.trials) for s in result.scenarios)
    if errored:
        first = (errored[0].error or "").splitlines()[0]
        sentence = f"{len(errored)} of {calls} calls could not run: {first}"
        return {"sentence": sentence, "tiles": []}
    problems = [p for s in result.scenarios for p in _problems(s, result)]
    if not problems:
        tail = (
            f" and nothing got worse than baseline {result.baseline_name}"
            if result.baseline_name
            else ""
        )
        noun = "call" if calls == 1 else "calls"
        return {"sentence": f"The agent passed every check in {calls} {noun}{tail}.", "tiles": []}
    phrases = list(dict.fromkeys(p["phrase"] for p in sorted(problems, key=_order)))
    failing = [s for s in result.scenarios if not s.passed or _regressed(s, result)]
    where = (
        f" (in {len(failing)} of {len(result.scenarios)} scenarios)"
        if len(result.scenarios) > 1
        else ""
    )
    sentence = f"The agent {_join(phrases)}{where}."
    tiles: list[dict[str, Any]] = []
    for p in sorted(problems, key=_order):
        if all(t["title"] != p["title"] for t in tiles):
            tiles.append({k: v for k, v in p.items() if k != "phrase"})
    return {"sentence": sentence, "tiles": tiles[:3]}


def summarize_scenario(scenario: ScenarioResult, result: RunResult) -> str:
    """One sentence for one scenario, in the same words as the run's."""
    problems = sorted(_problems(scenario, result), key=_order)
    if not problems:
        return "Passed every check."
    return f"The agent {_join(list(dict.fromkeys(p['phrase'] for p in problems)))}."


def _problems(scenario: ScenarioResult, result: RunResult) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for a in scenario.aggregates:
        kind = _KINDS.get(a.name)
        if kind is None or a.passed is not False:
            continue
        out.append(_problem(scenario, a, kind, _fmt(a.value, a.unit), _fmt(a.threshold, a.unit)))
    regressed = [
        d for d in result.baseline_diff if d.scenario_id == scenario.scenario_id and d.regressed
    ]
    # One regression per scenario: the most telling number (p95 before p50, and so on).
    regressed.sort(key=lambda d: list(_NAMES).index(d.metric) if d.metric in _NAMES else 99)
    for d in regressed[:1]:
        moved = scenario.aggregate(d.metric)
        if moved is not None and not any(p["metric"] == d.metric for p in out):
            out.append(_regression(scenario, moved, d, result.baseline_name or "baseline"))
    covered = {p["finding"] for p in out}
    for reason in scenario.failure_reasons:
        for key, phrase in _STRUCTURAL:
            if key in reason and key not in covered:
                covered.add(key)
                out.append(
                    {
                        "metric": key,
                        "finding": key,
                        "title": phrase[0].upper() + phrase[1:],
                        "phrase": phrase,
                        "weight": 5,
                        "scenario_id": scenario.scenario_id,
                        "value": None,
                        "limit": None,
                        "detail": reason.split(": ", 1)[-1],
                        **_locate(scenario.trials, key),
                    }
                )
    if not out and not scenario.passed:
        # Nothing above explains the failure (an older run without across-call numbers):
        # say what the calls themselves reported, never "passed".
        scored = [t for t in scenario.trials if t.error is None]
        failed = [t for t in scored if not t.passed]
        first = next((r for t in failed for r in t.failure_reasons), "a check failed")
        out.append(
            {
                "metric": "",
                "finding": "",
                "title": "Failed checks",
                "phrase": f"fails checks in {len(failed)} of {len(scored)} calls ({first})",
                "weight": 9,
                "scenario_id": scenario.scenario_id,
                "value": None,
                "limit": None,
                "detail": first,
                "call_id": failed[0].call_id if failed else None,
                "t_s": None,
                "trial": failed[0].trial if failed else None,
            }
        )
    return out


def _problem(
    scenario: ScenarioResult, a: Aggregate, kind: _Kind, value: str, limit: str
) -> dict[str, Any]:
    return {
        "metric": a.name,
        "finding": kind.finding,
        "title": kind.title,
        "phrase": kind.phrase.format(v=value, limit=limit),
        "weight": kind.weight,
        "scenario_id": scenario.scenario_id,
        "value": value,
        "limit": f"{'≤' if a.comparator == '<=' else '≥'} {limit}",
        "detail": _how_often(scenario.trials, a),
        **_locate(scenario.trials, kind.finding, a.name),
    }


def _regression(
    scenario: ScenarioResult, a: Aggregate, d: BaselineDiff, name: str
) -> dict[str, Any]:
    kind = _KINDS.get(a.name)
    label = _NAMES.get(a.name, a.name)
    old, new = _fmt(d.baseline, a.unit), _fmt(d.current, a.unit)
    return {
        "metric": a.name,
        "finding": kind.finding if kind else a.name,
        "title": f"Worse than {name}",
        "phrase": f"got worse than {name} ({label}: {old} → {new})",
        "weight": 2.5,
        "scenario_id": scenario.scenario_id,
        "value": new,
        "limit": f"was {old}",
        "detail": "beyond run-to-run noise",
        **_locate(scenario.trials, kind.finding if kind else "", a.name),
    }


def _how_often(trials: list[TrialResult], a: Aggregate) -> str:
    """ "in 12 of 12 replies" for per-turn metrics, "in 2 of 3 calls" otherwise."""
    scored = [t for t in trials if t.error is None]
    if a.name in ("response_latency_p95_s", "time_to_yield_p95_s") and a.threshold is not None:
        samples = [s for t in scored if (m := t.metric(a.name)) for s in m.samples]
        over = sum(s > a.threshold for s in samples)
        noun = "replies" if a.name.startswith("response") else "interruptions"
        return f"{over} of {len(samples)} {noun} over the limit"
    source = next(spec.source for spec in SPECS if spec.name == a.name)
    failed = sum(1 for t in scored if (m := t.metric(source)) is not None and m.passed is False)
    return f"in {failed} of {len(scored)} calls"


def _locate(trials: list[TrialResult], finding: str, metric: str = "") -> dict[str, Any]:
    """Where to hear it: the first failing finding of this kind, else the worst sample
    of the metric (a regression can be under the limit, so nothing "failed")."""
    for t in trials:
        for f in t.findings:
            if f.metric == finding and f.severity == "fail":
                return {"call_id": t.call_id, "t_s": f.t_s, "trial": t.trial}
    worst: tuple[float, TrialResult, float] | None = None
    for t in trials:
        m = t.metric(metric) if metric else None
        if m is None or len(m.sample_times_s) != len(m.samples):
            continue
        for v, at in zip(m.samples, m.sample_times_s, strict=True):
            if worst is None or v > worst[0]:
                worst = (v, t, at)
    if worst is not None:
        return {"call_id": worst[1].call_id, "t_s": worst[2], "trial": worst[1].trial}
    return {"call_id": None, "t_s": None, "trial": None}


def _regressed(scenario: ScenarioResult, result: RunResult) -> bool:
    return any(d.regressed and d.scenario_id == scenario.scenario_id for d in result.baseline_diff)


def _order(p: dict[str, Any]) -> tuple[float, str]:
    return (float(p["weight"]), str(p["scenario_id"]))


def _join(phrases: list[str]) -> str:
    if len(phrases) <= 1:
        return "".join(phrases)
    return ", ".join(phrases[:-1]) + " and " + phrases[-1]


def _fmt(v: float | None, unit: str) -> str:
    if v is None:
        return "–"
    if unit == "s":
        return f"{v:.2f}".rstrip("0").rstrip(".") + " s"
    if unit == "ratio":
        pct = v * 100
        return f"{pct:.1f}%" if 0 < pct < 10 and pct != int(pct) else f"{round(pct)}%"
    return f"{v:g}"
