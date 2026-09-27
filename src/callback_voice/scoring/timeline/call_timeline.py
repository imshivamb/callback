from dataclasses import dataclass, field

from callback_voice.core.models.call_event import CallEvent
from callback_voice.scoring.timeline.caller_utterance import CallerUtterance
from callback_voice.scoring.timeline.segment import Segment


@dataclass(frozen=True, slots=True)
class CallTimeline:
    """Everything metrics need, in seconds on the recording clock."""

    duration_s: float
    agent_speech: list[Segment]
    caller_speech: list[Segment]
    utterances: list[CallerUtterance]
    events: list[CallEvent] = field(default_factory=list)

    def agent_speaking_at(self, t_s: float, margin_s: float = 0.0) -> Segment | None:
        return next((s for s in self.agent_speech if s.contains(t_s, margin_s)), None)

    def next_agent_onset(self, after_s: float) -> Segment | None:
        return next((s for s in self.agent_speech if s.start_s >= after_s), None)
