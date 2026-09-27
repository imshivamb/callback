from datetime import datetime

from pydantic import Field

from callback_voice.core.models.aggregate import Aggregate
from callback_voice.core.models.strict_model import RecordModel


class Baseline(RecordModel):
    """A saved run's scenario aggregates, the reference later runs are compared with."""

    schema_version: int = 1
    name: str
    saved_at: datetime
    run_id: str
    git_sha: str | None = None
    agent_config_hash: str
    scenarios: dict[str, list[Aggregate]] = Field(default_factory=dict)
