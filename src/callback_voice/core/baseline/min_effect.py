from collections.abc import Mapping
from typing import Final

from callback_voice.errors import ConfigError
from callback_voice.scoring.aggregate.aggregate_spec import SPECS

DEFAULT_MIN_EFFECT: Final[Mapping[str, float]] = {
    # Bootstrap intervals on latency are tight (±10–20 ms on a few calls), so without
    # a floor, ordinary run-to-run jitter of the same agent would count as a regression.
    "response_latency_p95_s": 0.1,
    "response_latency_p50_s": 0.1,
    "time_to_yield_p95_s": 0.1,
    "talk_over_ratio": 0.02,
    "silence_reprompt_s": 1.0,
}


def min_effect(configured: Mapping[str, float]) -> dict[str, float]:
    """Smallest change per aggregate that can count as a regression.

    ``min_effect`` in callback.yaml overrides the defaults; unknown names are a config
    error, so a typo cannot silently switch a check off.
    """
    known = {s.name for s in SPECS}
    unknown = sorted(set(configured) - known)
    if unknown:
        raise ConfigError(
            f"min_effect: unknown metric(s) {', '.join(unknown)}",
            hint=f"known: {', '.join(sorted(known))}",
        )
    return {**DEFAULT_MIN_EFFECT, **configured}
