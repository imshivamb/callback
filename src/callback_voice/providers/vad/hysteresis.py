from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class VadParams:
    """Thresholds turning per-window probabilities into speech segments.

    Speech starts once probability stays >= ``start_threshold`` for ``min_speech_s``;
    it ends once probability stays < ``end_threshold`` for ``min_silence_s``. Edges
    are back-dated to the first/last qualifying window, so timings are not delayed
    by the confirmation periods.
    """

    start_threshold: float = 0.5
    end_threshold: float = 0.35
    min_speech_s: float = 0.09
    min_silence_s: float = 0.25


@dataclass(frozen=True, slots=True)
class SpeechEdge:
    kind: Literal["start", "end"]
    t_s: float


class HysteresisTracker:
    """Feeds window probabilities one at a time and emits confirmed speech edges."""

    def __init__(self, window_s: float, params: VadParams = VadParams()) -> None:
        self._window_s = window_s
        self._p = params
        self._index = 0
        self.speaking = False
        self._candidate_start: int | None = None
        self._last_speech_end: int = 0
        self._speech_started_at: float = 0.0

    @property
    def now_s(self) -> float:
        return self._index * self._window_s

    @property
    def speech_duration_s(self) -> float:
        """How long the current confirmed speech run has lasted (0 when silent)."""
        return self.now_s - self._speech_started_at if self.speaking else 0.0

    def step(self, probability: float) -> SpeechEdge | None:
        i = self._index
        self._index += 1
        if not self.speaking:
            if probability >= self._p.start_threshold:
                if self._candidate_start is None:
                    self._candidate_start = i
                if (self._index - self._candidate_start) * self._window_s >= self._p.min_speech_s:
                    self.speaking = True
                    self._speech_started_at = self._candidate_start * self._window_s
                    self._last_speech_end = self._index
                    self._candidate_start = None
                    return SpeechEdge("start", self._speech_started_at)
            else:
                self._candidate_start = None
            return None
        if probability >= self._p.end_threshold:
            self._last_speech_end = self._index
            return None
        if (self._index - self._last_speech_end) * self._window_s >= self._p.min_silence_s:
            self.speaking = False
            return SpeechEdge("end", self._last_speech_end * self._window_s)
        return None

    def flush(self) -> SpeechEdge | None:
        """Close an open speech run at end of stream."""
        if not self.speaking:
            return None
        self.speaking = False
        return SpeechEdge("end", self._last_speech_end * self._window_s)
