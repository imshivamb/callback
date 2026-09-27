from typing import Literal

from pydantic import Field

from callback_voice.core.models.strict_model import RecordModel

type Speaker = Literal["caller", "agent"]


class TurnWord(RecordModel):
    """One transcribed word with the recogniser's confidence (0–1)."""

    text: str
    start_s: float
    end_s: float
    p: float


class Turn(RecordModel):
    """A stretch of one side's speech, reconstructed from the recording."""

    speaker: Speaker
    start_s: float
    end_s: float
    text: str = ""
    interrupted_by: str | None = None
    chaos_ids: list[str] = Field(default_factory=list)
    words: list[TurnWord] = Field(default_factory=list)

    @property
    def confidence(self) -> float | None:
        """Mean word confidence of the transcription, when word scores exist."""
        return sum(w.p for w in self.words) / len(self.words) if self.words else None

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s
