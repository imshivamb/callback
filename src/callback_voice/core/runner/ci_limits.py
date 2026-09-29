import os

from callback_voice.core.models.limit_override import LimitOverride
from callback_voice.core.models.scenario import Scenario
from callback_voice.errors import ConfigError

CI_LATENCY_ENV = "CALLBACK_CI_LATENCY_LIMIT_S"
CI_DRIFT_ENV = "CALLBACK_CI_DRIFT_LIMIT_S"
CI_YIELD_ENV = "CALLBACK_CI_YIELD_LIMIT_S"
# environment variable -> (threshold field, metric it applies to)
_CI_LIMITS = {
    CI_LATENCY_ENV: ("response_latency_p95_s", "response_latency_p95_s"),
    CI_DRIFT_ENV: ("chaos_drift_s", "chaos_drift_max_s"),
    CI_YIELD_ENV: ("time_to_yield_p95_s", "time_to_yield_p95_s"),
}


def apply_ci_limits(scenarios: list[Scenario]) -> tuple[list[Scenario], list[LimitOverride]]:
    """Loosen limits on slow shared CI machines, and say so.

    ``CALLBACK_CI_LATENCY_LIMIT_S`` raises the reply-delay limit,
    ``CALLBACK_CI_YIELD_LIMIT_S`` the time-to-yield limit and
    ``CALLBACK_CI_DRIFT_LIMIT_S`` the chaos-timing tolerance to at least the given
    seconds. Neither is set by default; each can only loosen a limit, and every change
    is returned so it can be recorded in results.json and shown in the report: a CI
    limit must never be mistaken for the real target.
    """
    overrides: list[LimitOverride] = []
    for env, (field, metric) in _CI_LIMITS.items():
        raw = os.environ.get(env)
        if not raw:
            continue
        try:
            ci_limit = float(raw)
        except ValueError as exc:
            raise ConfigError(f"{env}={raw!r} is not a number of seconds") from exc
        if ci_limit <= 0:
            raise ConfigError(f"{env} must be positive, got {raw}")
        loosened: list[Scenario] = []
        for s in scenarios:
            target = float(getattr(s.expect.thresholds, field))
            if ci_limit <= target:
                loosened.append(s)
                continue
            update: dict[str, float] = {field: ci_limit}
            if field == "time_to_yield_p95_s" and s.expect.thresholds.talk_over_grace_s is None:
                update["talk_over_grace_s"] = target  # talk-over keeps the real target
            thresholds = s.expect.thresholds.model_copy(update=update)
            expect = s.expect.model_copy(update={"thresholds": thresholds})
            loosened.append(s.model_copy(update={"expect": expect}))
            overrides.append(
                LimitOverride(
                    scenario_id=s.id, metric=metric, target=target, applied=ci_limit, source=env
                )
            )
        scenarios = loosened
    return scenarios, overrides
