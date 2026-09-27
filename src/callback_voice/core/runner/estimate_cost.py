from dataclasses import dataclass

from callback_voice.core.models.scenario import Scenario

_TURNS_PER_CALL = 14
_TOKENS_PER_TURN = 1_400  # the whole chat is resent each turn
_JUDGE_TOKENS_PER_CALL = 3_000


@dataclass(frozen=True, slots=True)
class CostEstimate:
    calls: int
    llm_calls: int
    judge_calls: int
    max_minutes: float
    usd: float


def estimate_cost(
    plan: list[tuple[Scenario, int]],
    caller_usd_per_1k: float,
    *,
    replaying: bool,
    judge_usd_per_1k: float | None,
) -> CostEstimate:
    """Upper-bound estimate printed before a run: calls, minutes and LLM spend.

    Scripted callers and replayed cassettes make no caller LLM calls. The judge,
    when configured, makes one call per trial.
    """
    llm_calls = 0 if replaying else sum(1 for scenario, _ in plan if scenario.caller.script is None)
    judge_calls = len(plan) if judge_usd_per_1k is not None else 0
    usd = (
        llm_calls * _TURNS_PER_CALL * _TOKENS_PER_TURN / 1000 * caller_usd_per_1k
        + judge_calls * _JUDGE_TOKENS_PER_CALL / 1000 * (judge_usd_per_1k or 0.0)
    )
    return CostEstimate(
        calls=len(plan),
        llm_calls=llm_calls,
        judge_calls=judge_calls,
        max_minutes=round(sum(s.max_duration_s for s, _ in plan) / 60, 1),
        usd=round(usd, 4),
    )
