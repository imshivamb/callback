from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Literal

from callback_voice.core.models.metric import Comparator
from callback_voice.core.models.thresholds import Thresholds

type Reducer = Literal["rate", "pooled_p95", "pooled_p50", "mean", "max"]


@dataclass(frozen=True, slots=True)
class AggregateSpec:
    """How one per-call metric becomes a scenario-level number.

    ``rate``: share of calls where the metric passed (Wilson interval).
    ``pooled_p95``/``pooled_p50``: percentile of every per-turn sample from every call
    (cluster bootstrap interval). ``mean``/``max``: across calls' values.
    """

    name: str
    source: str
    reducer: Reducer
    unit: str
    comparator: Comparator
    threshold: Callable[[Thresholds], float] | None


SPECS: Final[tuple[AggregateSpec, ...]] = (
    AggregateSpec(
        "task_success_rate", "task_success", "rate", "ratio", ">=", lambda t: t.task_success_rate
    ),
    AggregateSpec(
        "response_latency_p95_s",
        "response_latency_p95_s",
        "pooled_p95",
        "s",
        "<=",
        lambda t: t.response_latency_p95_s,
    ),
    AggregateSpec(
        "response_latency_p50_s", "response_latency_p50_s", "pooled_p50", "s", "<=", None
    ),
    AggregateSpec(
        "time_to_yield_p95_s",
        "time_to_yield_p95_s",
        "pooled_p95",
        "s",
        "<=",
        lambda t: t.time_to_yield_p95_s,
    ),
    AggregateSpec(
        "talk_over_ratio", "talk_over_ratio", "mean", "ratio", "<=", lambda t: t.talk_over_ratio
    ),
    AggregateSpec("false_yields", "false_yields", "max", "count", "<=", lambda t: t.false_yields),
    AggregateSpec(
        "silence_reprompt_s", "silence_reprompt_s", "max", "s", "<=", lambda t: t.silence_reprompt_s
    ),
    AggregateSpec(
        "entity_fidelity", "entity_fidelity", "mean", "ratio", ">=", lambda t: t.entity_fidelity
    ),
    AggregateSpec(
        "policy_violations",
        "policy_violations",
        "max",
        "count",
        "<=",
        lambda t: t.policy_violations,
    ),
    AggregateSpec(
        "unanswered_turns",
        "unanswered_turns",
        "max",
        "count",
        "<=",
        lambda t: t.unanswered_turns,
    ),
    AggregateSpec("rules_not_checked", "rules_not_checked", "max", "count", "<=", None),
    AggregateSpec("call_pass_rate", "", "rate", "ratio", ">=", None),
)
