from dataclasses import dataclass

from callback_voice.core.models.scenario import Scenario

_TURNS_PER_CALL = 14
_TOKENS_PER_TURN = 1_400  # the whole chat is resent each turn


@dataclass(frozen=True, slots=True)
class CostEstimate:
    calls: int
    llm_calls: int
    max_minutes: float
    usd: float


def estimate_cost(
    plan: list[tuple[Scenario, int]], usd_per_1k_tokens: float, *, replaying: bool
) -> CostEstimate:
    """Upper-bound estimate printed before a run: calls, minutes and LLM spend.

    Scripted callers and replayed cassettes make no LLM calls.
    """
    llm_calls = 0 if replaying else sum(1 for scenario, _ in plan if scenario.caller.script is None)
    tokens = llm_calls * _TURNS_PER_CALL * _TOKENS_PER_TURN
    return CostEstimate(
        calls=len(plan),
        llm_calls=llm_calls,
        max_minutes=round(sum(s.max_duration_s for s, _ in plan) / 60, 1),
        usd=round(tokens / 1000 * usd_per_1k_tokens, 4),
    )
