from datetime import datetime

from pydantic import Field

from callback_voice.core.models.call_event import CallEvent
from callback_voice.core.models.strict_model import RecordModel
from callback_voice.core.models.turn import Turn


class CallRecord(RecordModel):
    """Everything captured about one call. Paths are relative to the run directory."""

    call_id: str
    scenario_id: str
    trial: int
    seed: int
    transport: str
    started_at: datetime
    duration_s: float
    end_reason: str
    wav_path: str
    events: list[CallEvent] = Field(default_factory=list)
    transcript: list[Turn] = Field(default_factory=list)
    speech: list[Turn] = Field(default_factory=list)
    """Both sides' speech as the scorer measured it on the recording (VAD edges), with
    the caller's line or the agent's transcribed words where known. The report draws
    these, so it shows exactly what the metrics were computed from."""
