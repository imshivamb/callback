import numpy as np

from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.providers.vad.base import VoiceActivityModel
from callback_voice.providers.vad.hysteresis import HysteresisTracker, SpeechEdge, VadParams


class SpeechDetector:
    """Streaming speech start/end detection over arbitrarily sized audio chunks.

    Times are seconds since the first sample pushed. Used live by the caller (to
    follow the agent's turns) and by the reference agents (to hear the caller).
    """

    def __init__(self, model: VoiceActivityModel, params: VadParams = VadParams()) -> None:
        self._model = model
        self._model.reset()
        self._tracker = HysteresisTracker(model.window_samples / SAMPLE_RATE, params)
        self._pending = np.zeros(0, dtype=np.float32)
        self.last_probability = 0.0

    @property
    def speaking(self) -> bool:
        return self._tracker.speaking

    @property
    def speech_duration_s(self) -> float:
        return self._tracker.speech_duration_s

    @property
    def now_s(self) -> float:
        return self._tracker.now_s

    def push(self, audio: Audio) -> list[SpeechEdge]:
        buffer = np.concatenate([self._pending, audio]) if self._pending.size else audio
        width = self._model.window_samples
        whole = buffer.size - buffer.size % width
        edges: list[SpeechEdge] = []
        for offset in range(0, whole, width):
            self.last_probability = self._model.probability(buffer[offset : offset + width])
            edge = self._tracker.step(self.last_probability)
            if edge is not None:
                edges.append(edge)
        self._pending = buffer[whole:].copy()
        return edges
