from typing import Literal

from pydantic import Field

from callback_voice.core.models.strict_model import RecordModel

type Speaker = Literal["caller", "agent"]


class Turn(RecordModel):
    """A stretch of one side's speech, reconstructed from the recording."""

    speaker: Speaker
    start_s: float
    end_s: float
    text: str = ""
    interrupted_by: str | None = None
    chaos_ids: list[str] = Field(default_factory=list)

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s
