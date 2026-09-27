from typing import Protocol

from callback_voice.audio.format import Audio
from callback_voice.caller.engine.utterance import UtteranceTag
from callback_voice.core.models.chaos_event import ChaosEvent


class ChaosContext(Protocol):
    """The live call as a chaos processor sees it. Implemented by the call session."""

    @property
    def t_s(self) -> float: ...

    @property
    def agent_turn(self) -> int: ...

    @property
    def agent_in_turn(self) -> bool: ...

    @property
    def agent_speaking(self) -> bool: ...

    @property
    def elapsed_in_agent_turn(self) -> float: ...

    @property
    def caller_speaking(self) -> bool: ...

    def interject(
        self, audio: Audio, text: str, tag: UtteranceTag, event: ChaosEvent, intended_s: float
    ) -> None:
        """Put pre-rendered audio on the wire starting next tick, cutting in."""
        ...

    def note(self, event: ChaosEvent, t_s: float, **data: object) -> None:
        """Log that a chaos event acted (for window effects and caller-turn rewrites)."""
        ...
