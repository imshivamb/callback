from typing import Any, Literal

from pydantic import Field

from callback_voice.core.models.strict_model import RecordModel

type EventKind = Literal[
    "call_start",
    "call_end",
    "caller_utterance",
    "agent_turn_start",
    "agent_turn_end",
    "chaos",
    "dtmf",
    "clock_drift",
    "note",
]


class CallEvent(RecordModel):
    """One entry in a call's event log. Times are seconds on the recording clock.

    ``intended_s`` is when a chaos action was scheduled to hit the wire; comparing it
    to ``t_s`` exposes caller-pipeline lag (flagged above 100 ms).
    """

    t_s: float
    kind: EventKind
    chaos_id: str | None = None
    chaos_type: str | None = None
    intended_s: float | None = None
    end_s: float | None = None
    text: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
