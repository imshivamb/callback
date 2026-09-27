from collections import deque

import numpy as np

from callback_voice.audio.format import FRAME_SAMPLES, Audio


class PlayoutBuffer:
    """What the caller hears, one 20 ms frame per tick.

    Inbound agent audio is queued as it arrives and played out at real time, with
    silence when nothing is buffered, like a phone's jitter buffer. An agent that
    sends faster than real time therefore keeps "talking" until its buffered audio
    has played, which is exactly what a human caller would hear.
    """

    def __init__(self) -> None:
        self._chunks: deque[Audio] = deque()
        self._buffered = 0

    @property
    def buffered_s(self) -> float:
        return self._buffered / (FRAME_SAMPLES * 50)

    def push(self, chunk: Audio) -> None:
        if chunk.size:
            self._chunks.append(chunk)
            self._buffered += chunk.size

    def pop_frame(self) -> Audio:
        frame = np.zeros(FRAME_SAMPLES, dtype=np.float32)
        filled = 0
        while filled < FRAME_SAMPLES and self._chunks:
            head = self._chunks[0]
            take = min(FRAME_SAMPLES - filled, head.size)
            frame[filled : filled + take] = head[:take]
            filled += take
            if take == head.size:
                self._chunks.popleft()
            else:
                self._chunks[0] = head[take:]
        self._buffered -= filled
        return frame
