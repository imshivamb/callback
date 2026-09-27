import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable

import numpy as np

from callback_voice.audio.format import FRAME_S, FRAME_SAMPLES, Audio, silence
from callback_voice.audio.pcm import to_pcm16

_SENTENCE_GAP_S = 0.18


class PacedSpeaker:
    """Streams queued sentences to the caller in real time, 20 ms per frame.

    Pacing matters: an agent that dumps audio faster than real time cannot stop
    talking when interrupted, because the audio is already on the wire.
    """

    def __init__(self, send: Callable[[bytes], Awaitable[None]]) -> None:
        self._send = send
        self._queue: deque[Audio] = deque()
        self._wake = asyncio.Event()
        self.idle = asyncio.Event()
        self.idle.set()
        self._stop_now = False
        self.sentence_index = -1
        self.speaking = False
        self.last_spoke_at = time.monotonic()

    def begin_reply(self) -> None:
        """Start numbering sentences from zero for a new reply."""
        self.sentence_index = -1

    def enqueue(self, sentence: Audio) -> None:
        self._queue.append(sentence)
        self.idle.clear()
        self._wake.set()

    def stop(self) -> None:
        """Stop mid-frame and drop everything queued (the agent yields)."""
        self._queue.clear()
        self._stop_now = True

    @property
    def busy(self) -> bool:
        return self.speaking or bool(self._queue)

    async def run(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            while self._queue:
                sentence = self._queue.popleft()
                self.sentence_index += 1
                self._stop_now = False
                self.speaking = True
                gap = silence(_SENTENCE_GAP_S) if self._queue else np.zeros(0, np.float32)
                await self._play(np.concatenate([sentence, gap]))
                self.speaking = False
                self.last_spoke_at = time.monotonic()
                if self._stop_now:
                    break
            self.idle.set()

    async def _play(self, audio: Audio) -> None:
        start = time.monotonic()
        for n, offset in enumerate(range(0, audio.size, FRAME_SAMPLES)):
            if self._stop_now:
                return
            await self._send(to_pcm16(audio[offset : offset + FRAME_SAMPLES]))
            delay = start + (n + 1) * FRAME_S - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
