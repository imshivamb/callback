from pydantic import Field

from callback_voice.core.models.strict_model import StrictModel


class Thresholds(StrictModel):
    """Pass/fail limits for deterministic metrics, with conservative defaults for phone calls."""

    response_latency_p95_s: float = Field(default=1.5, gt=0)
    time_to_yield_p95_s: float = Field(default=0.6, gt=0)
    talk_over_ratio: float = Field(default=0.05, ge=0, le=1)
    false_yields: int = Field(default=0, ge=0)
    silence_reprompt_s: float = Field(default=8.0, gt=0)
    task_success_rate: float = Field(default=0.8, ge=0, le=1)
    entity_fidelity: float = Field(default=1.0, ge=0, le=1)
    policy_violations: int = Field(default=0, ge=0)
