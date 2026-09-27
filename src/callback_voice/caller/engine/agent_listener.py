from dataclasses import dataclass

from callback_voice.audio.format import Audio
from callback_voice.providers.vad.base import VoiceActivityModel
from callback_voice.providers.vad.hysteresis import VadParams
from callback_voice.providers.vad.speech_detector import SpeechDetector

_NEW_TURN_AFTER_SILENCE_S = 3.0


@dataclass(frozen=True, slots=True)
class AgentTurnStarted:
    turn: int
    t_s: float


@dataclass(frozen=True, slots=True)
class AgentTurnEnded:
    turn: int
    start_s: float
    end_s: float


type ListenerEvent = AgentTurnStarted | AgentTurnEnded


class AgentListener:
    """Follows the agent's turns from the audio the caller hears.

    An agent turn is everything the agent says between two caller turns: pauses
    between sentences do not end it, and a backchannel does not split it. A new turn
    begins when the agent speaks after the caller took the floor, or after 3 s of
    silence (a reprompt). A turn ends once the agent has been quiet for
    ``endpoint_s``, which is when a human caller would start to answer.

    This is live turn-following for the simulated caller only; metrics are computed
    later from the recording.
    """

    def __init__(self, vad: VoiceActivityModel, endpoint_s: float = 0.7) -> None:
        self._detector = SpeechDetector(vad, VadParams(min_silence_s=0.2))
        self._endpoint_s = endpoint_s
        self.turn = 0
        self.turn_start_s = 0.0
        self.in_turn = False
        self._last_speech_end: float | None = None
        self._floor_taken = False

    @property
    def speaking(self) -> bool:
        return self._detector.speaking

    def caller_took_floor(self) -> None:
        """The caller finished saying something that expects an answer."""
        self._floor_taken = True

    def elapsed_in_turn(self, t_s: float) -> float:
        return t_s - self.turn_start_s if self.in_turn else 0.0

    def hear(self, frame: Audio) -> list[ListenerEvent]:
        events: list[ListenerEvent] = []
        for edge in self._detector.push(frame):
            if edge.kind == "start":
                quiet_for = (
                    edge.t_s - self._last_speech_end if self._last_speech_end is not None else None
                )
                new_turn = not self.in_turn and (
                    self.turn == 0
                    or self._floor_taken
                    or (quiet_for is not None and quiet_for >= _NEW_TURN_AFTER_SILENCE_S)
                )
                if self.in_turn and self._floor_taken:
                    events.append(self._end_turn(self._last_speech_end or edge.t_s))
                    new_turn = True
                if new_turn:
                    self.turn += 1
                    self.turn_start_s = edge.t_s
                    self.in_turn = True
                    self._floor_taken = False
                    events.append(AgentTurnStarted(self.turn, edge.t_s))
                elif not self.in_turn:
                    self.in_turn = True  # agent resumed its turn after a short pause
                self._last_speech_end = None
            else:
                self._last_speech_end = edge.t_s
        now = self._detector.now_s
        if (
            self.in_turn
            and not self._detector.speaking
            and self._last_speech_end is not None
            and now - self._last_speech_end >= self._endpoint_s
        ):
            events.append(self._end_turn(self._last_speech_end))
        return events

    def _end_turn(self, end_s: float) -> AgentTurnEnded:
        self.in_turn = False
        return AgentTurnEnded(self.turn, self.turn_start_s, end_s)
