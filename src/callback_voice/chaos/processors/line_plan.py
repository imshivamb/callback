from dataclasses import dataclass, field
from typing import Any

from callback_voice.caller.engine.utterance import UtteranceTag


@dataclass(slots=True)
class LinePlan:
    """The caller's next turn, before it is rendered. Chaos may rewrite it."""

    text: str
    tag: UtteranceTag = "line"
    lead_silence_s: float = 0.0
    chaos_id: str | None = None
    chaos_type: str | None = None
    dtmf: str | None = None
    updates: dict[str, Any] = field(default_factory=dict)
    hang_up: bool = False
