from pydantic import Field

from callback_voice.core.models.aggregate import Aggregate
from callback_voice.core.models.strict_model import RecordModel
from callback_voice.core.models.trial_result import TrialResult


class ScenarioResult(RecordModel):
    """All trials of one scenario, with aggregates."""

    scenario_id: str
    agent: str
    source: str | None = None
    passed: bool
    trials: list[TrialResult] = Field(default_factory=list)
    aggregates: list[Aggregate] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)

    def aggregate(self, name: str) -> Aggregate | None:
        return next((a for a in self.aggregates if a.name == name), None)
