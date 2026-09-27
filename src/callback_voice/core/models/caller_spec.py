from typing import Any, Literal

from pydantic import Field, model_validator

from callback_voice.core.models.strict_model import StrictModel

type Patience = Literal["low", "medium", "high"]


class CallerSpec(StrictModel):
    """Who is calling and what they want.

    A caller is LLM-driven by default. Giving ``script`` makes it a scripted caller
    that says the lines in order, which needs no LLM at all.
    """

    persona: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    knows: dict[str, Any] = Field(default_factory=dict)
    language: str = "en"
    voice: str | None = None
    patience: Patience = "medium"
    speaking_rate: float = Field(default=1.0, gt=0.5, le=2.0)
    speaks_first: bool = False
    script: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def _script_not_empty(self) -> "CallerSpec":
        if self.script is not None and not self.script:
            raise ValueError("script must have at least one line")
        return self

    @property
    def failed_attempts_allowed(self) -> int:
        """How many unproductive exchanges the caller tolerates before hanging up."""
        return {"low": 2, "medium": 4, "high": 8}[self.patience]
