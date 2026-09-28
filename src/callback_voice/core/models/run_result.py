from datetime import datetime
from typing import Any

from pydantic import Field

from callback_voice.core.models.baseline_diff import BaselineDiff
from callback_voice.core.models.scenario_result import ScenarioResult
from callback_voice.core.models.strict_model import RecordModel


class RunResult(RecordModel):
    """The contents of ``results.json``: one invocation of ``callback run``."""

    schema_version: int = 1
    run_id: str
    created_at: datetime
    callback_version: str
    git_sha: str | None = None
    agent_config_hash: str
    mode: str
    concurrency: int = 1
    """Calls placed at once. Parallel calls on one machine compete for CPU and inflate
    latency, so runs are only comparable at the same concurrency."""
    providers: dict[str, str] = Field(default_factory=dict)
    judge: dict[str, Any] | None = None
    vad: dict[str, Any] = Field(default_factory=dict)
    scenarios: list[ScenarioResult] = Field(default_factory=list)
    baseline_name: str | None = None
    baseline_diff: list[BaselineDiff] = Field(default_factory=list)
    passed: bool
    exit_code: int
    duration_s: float = 0.0

    @property
    def trial_count(self) -> int:
        return sum(len(s.trials) for s in self.scenarios)
