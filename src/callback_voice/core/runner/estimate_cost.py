import math
from collections.abc import Mapping
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
    phone_calls: int = 0
    phone_usd: float = 0.0


def estimate_cost(
    plan: list[tuple[Scenario, int]],
    caller_usd_per_1k: float,
    *,
    replaying: bool,
    judge_usd_per_1k: float | None,
    phone_usd_per_minute: Mapping[str, float] | None = None,
) -> CostEstimate:
    """Upper-bound estimate printed before a run: calls, minutes, LLM and phone spend.

    Scripted callers and replayed cassettes make no caller LLM calls. The judge,
    when configured, makes one call per trial. ``phone_usd_per_minute`` maps each
    phone target to its rate; a phone call is billed per started minute, so each call
    counts its ``max_duration_s`` rounded up to whole minutes.
    """
    rates = phone_usd_per_minute or {}
    phone = [s for s, _ in plan if s.agent in rates]
    phone_usd = sum(math.ceil(s.max_duration_s / 60) * rates[s.agent] for s in phone)
    llm_calls = 0 if replaying else sum(1 for scenario, _ in plan if scenario.caller.script is None)
    judge_calls = len(plan) if judge_usd_per_1k is not None else 0
    usd = (
        llm_calls * _TURNS_PER_CALL * _TOKENS_PER_TURN / 1000 * caller_usd_per_1k
        + judge_calls * _JUDGE_TOKENS_PER_CALL / 1000 * (judge_usd_per_1k or 0.0)
        + phone_usd
    )
    return CostEstimate(
        calls=len(plan),
        llm_calls=llm_calls,
        judge_calls=judge_calls,
        max_minutes=round(sum(s.max_duration_s for s, _ in plan) / 60, 1),
        usd=round(usd, 4),
        phone_calls=len(phone),
        phone_usd=round(phone_usd, 4),
    )
