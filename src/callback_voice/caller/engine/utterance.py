from dataclasses import dataclass, field
from typing import Literal

from callback_voice.audio.format import Audio

type UtteranceTag = Literal[
    "line",
    "barge_in",
    "backchannel",
    "ask_for_human",
    "repeat_request",
    "change_mind",
    "dtmf",
    "nudge",
]
FLOOR_TAKING: frozenset[UtteranceTag] = frozenset(
    {"line", "barge_in", "ask_for_human", "repeat_request", "change_mind", "nudge"}
)


@dataclass(slots=True)
class Utterance:
    """Audio the caller will put on the wire, with why it is being said.

    ``intended_s`` is when a chaos action wanted it to start; the event log keeps
    both so caller-pipeline lag is visible.
    """

    audio: Audio
    text: str
    tag: UtteranceTag = "line"
    chaos_id: str | None = None
    chaos_type: str | None = None
    intended_s: float | None = None
    lead_silence_s: float = 0.0
    data: dict[str, object] = field(default_factory=dict)

    @property
    def takes_floor(self) -> bool:
        """Whether the caller expects the agent to respond to this."""
        return self.tag in FLOOR_TAKING
