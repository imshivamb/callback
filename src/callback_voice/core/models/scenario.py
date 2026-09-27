from pathlib import Path

from pydantic import Field

from callback_voice.core.models.caller_spec import CallerSpec
from callback_voice.core.models.chaos_config import ChaosConfig
from callback_voice.core.models.expectation import Expectation
from callback_voice.core.models.strict_model import StrictModel


class Scenario(StrictModel):
    """One YAML file: who calls, what they want, how the call breaks, how it is judged."""

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$", max_length=120)
    agent: str = Field(min_length=1)
    trials: int = Field(default=1, ge=1, le=500)
    max_duration_s: float = Field(default=180.0, gt=5, le=1800)
    caller: CallerSpec
    chaos: ChaosConfig = Field(default_factory=ChaosConfig)
    expect: Expectation = Field(default_factory=Expectation)
    source: Path | None = Field(default=None, exclude=True)
