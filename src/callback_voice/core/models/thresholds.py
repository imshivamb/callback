from pydantic import Field

from callback_voice.core.models.strict_model import StrictModel


class Thresholds(StrictModel):
    """Pass/fail limits for deterministic metrics, with conservative defaults for phone calls."""

    response_latency_p95_s: float = Field(default=1.5, gt=0)
    time_to_yield_p95_s: float = Field(default=0.6, gt=0)
    talk_over_grace_s: float | None = Field(default=None, gt=0)
    """How long after the caller cuts in the agent may keep talking before it counts as
    talk-over. Defaults to the time-to-yield limit; its own setting, so loosening that
    limit on CI doesn't loosen talk-over."""
    talk_over_ratio: float = Field(default=0.05, ge=0, le=1)
    false_yields: int = Field(default=0, ge=0)
    silence_reprompt_s: float = Field(default=8.0, gt=0)
    task_success_rate: float = Field(default=0.8, ge=0, le=1)
    entity_fidelity: float = Field(default=1.0, ge=0, le=1)
    policy_violations: int = Field(default=0, ge=0)
    unanswered_turns: int = Field(default=0, ge=0)
    unanswered_wait_s: float = Field(default=1.5, gt=0)
    """How long the caller must wait in silence before a turn counts as unanswered.
    Its own setting, so loosening the reply-delay limit (on CI) doesn't loosen it."""
    chaos_drift_s: float = Field(default=0.1, gt=0)
    """How late a chaos action may land (a Callback self-check; informational)."""
