from pydantic import Field

from callback_voice.core.models.call_record import CallRecord
from callback_voice.core.models.finding import Finding
from callback_voice.core.models.llm_usage import LlmUsage
from callback_voice.core.models.metric import Metric
from callback_voice.core.models.review_item import ReviewItem
from callback_voice.core.models.strict_model import RecordModel
from callback_voice.core.models.verifier_result import VerifierResult


class TrialResult(RecordModel):
    """Scored outcome of one call.

    ``error`` is set when the call could not run or be scored; such a trial is never
    a pass and makes the run exit with code 2.
    """

    call_id: str
    scenario_id: str
    trial: int
    seed: int
    passed: bool
    metrics: list[Metric] = Field(default_factory=list)
    verifier_results: list[VerifierResult] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)
    review: list[ReviewItem] = Field(default_factory=list)
    error: str | None = None
    call: CallRecord | None = None
    llm_usage: dict[str, LlmUsage] = Field(default_factory=dict)
    """What the caller and the judge LLMs were actually asked for in this call."""

    def metric(self, name: str) -> Metric | None:
        return next((m for m in self.metrics if m.name == name), None)
