from collections import deque
from collections.abc import Callable

import numpy as np

from callback_voice.audio.format import FRAME_S, FRAME_SAMPLES, SAMPLE_RATE, Audio
from callback_voice.caller.engine.utterance import Utterance

type UtteranceDone = Callable[[Utterance, float, float], None]


class CallerVoice:
    """The caller's mouth: plays queued utterances frame by frame.

    ``say(..., interrupt=True)`` starts on the very next tick, cutting off whatever
    is playing, because a barge-in or backchannel must land at its moment. Each
    utterance reports its actual start and end on the tick clock when it ends.
    """

    def __init__(self, on_done: UtteranceDone) -> None:
        self._queue: deque[Utterance] = deque()
        self._preempt: Utterance | None = None
        self._current: Utterance | None = None
        self._audio = np.zeros(0, dtype=np.float32)
        self._pos = 0
        self._lead = 0
        self._started_at = 0.0
        self._on_done = on_done

    @property
    def speaking(self) -> bool:
        """Producing speech this tick (lead-in silence does not count)."""
        return self._current is not None and self._pos >= self._lead

    @property
    def busy(self) -> bool:
        return self._current is not None or self._preempt is not None or bool(self._queue)

    @property
    def current(self) -> Utterance | None:
        return self._current

    def say(self, utterance: Utterance, *, interrupt: bool = False) -> None:
        if interrupt:
            self._preempt = utterance
        else:
            self._queue.append(utterance)

    def next_frame(self, t_s: float) -> Audio:
        """Clean caller audio for the tick starting at ``t_s``."""
        if self._preempt is not None:
            if self._current is not None:
                self._finish(end_s=t_s, truncated=True)
            self._begin(self._preempt, t_s)
            self._preempt = None
        elif self._current is None and self._queue:
            self._begin(self._queue.popleft(), t_s)
        frame = np.zeros(FRAME_SAMPLES, dtype=np.float32)
        if self._current is None:
            return frame
        chunk = self._audio[self._pos : self._pos + FRAME_SAMPLES]
        frame[: chunk.size] = chunk
        self._pos += FRAME_SAMPLES
        if self._pos >= self._audio.size:
            self._finish(end_s=t_s + chunk.size / SAMPLE_RATE)
        return frame

    def _begin(self, utterance: Utterance, t_s: float) -> None:
        self._current = utterance
        self._lead = round(utterance.lead_silence_s / FRAME_S) * FRAME_SAMPLES
        self._audio = np.concatenate([np.zeros(self._lead, dtype=np.float32), utterance.audio])
        self._pos = 0
        self._started_at = t_s + self._lead / SAMPLE_RATE

    def _finish(self, end_s: float, truncated: bool = False) -> None:
        done, self._current = self._current, None
        if done is None:
            return
        if truncated:
            done.data["truncated"] = True
        if end_s > self._started_at:
            self._on_done(done, self._started_at, end_s)
