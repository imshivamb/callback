import os

from callback_voice.core.models.limit_override import LimitOverride
from callback_voice.core.models.scenario import Scenario
from callback_voice.errors import ConfigError

CI_LATENCY_ENV = "CALLBACK_CI_LATENCY_LIMIT_S"


def apply_ci_limits(scenarios: list[Scenario]) -> tuple[list[Scenario], list[LimitOverride]]:
    """Loosen the reply-delay limit on slow shared CI machines, and say so.

    ``CALLBACK_CI_LATENCY_LIMIT_S`` (set in a CI workflow, never by default) raises each
    scenario's ``response_latency_p95_s`` limit to at least that value. It can only
    loosen a limit, never tighten one, and every change is returned so it can be
    recorded in results.json and shown in the report: a CI limit must never be
    mistaken for the real target.
    """
    raw = os.environ.get(CI_LATENCY_ENV)
    if not raw:
        return scenarios, []
    try:
        ci_limit = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{CI_LATENCY_ENV}={raw!r} is not a number of seconds") from exc
    if ci_limit <= 0:
        raise ConfigError(f"{CI_LATENCY_ENV} must be positive, got {raw}")
    out: list[Scenario] = []
    overrides: list[LimitOverride] = []
    for s in scenarios:
        target = s.expect.thresholds.response_latency_p95_s
        if ci_limit <= target:
            out.append(s)
            continue
        thresholds = s.expect.thresholds.model_copy(update={"response_latency_p95_s": ci_limit})
        expect = s.expect.model_copy(update={"thresholds": thresholds})
        out.append(s.model_copy(update={"expect": expect}))
        overrides.append(
            LimitOverride(
                scenario_id=s.id,
                metric="response_latency_p95_s",
                target=target,
                applied=ci_limit,
                source=CI_LATENCY_ENV,
            )
        )
    return out, overrides
