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
        self.reply_played_s = 0.0
        """Audio played since the reply began, including pauses between sentences."""
        self.speaking = False
        self.last_spoke_at = time.monotonic()
        self._stop_at_s: float | None = None

    def begin_reply(self) -> None:
        """Start numbering sentences, and counting audio, from zero for a new reply."""
        self.sentence_index = -1
        self.reply_played_s = 0.0
        self._stop_at_s = None

    @property
    def stopping(self) -> bool:
        """A delayed stop is pending (``stop(after_s=...)``)."""
        return self._stop_at_s is not None

    def enqueue(self, sentence: Audio) -> None:
        self._queue.append(sentence)
        self.idle.clear()
        self._wake.set()

    def stop(self, after_s: float = 0.0) -> None:
        """Stop and drop everything queued (the agent yields).

        With ``after_s``, keep playing that much more audio first, as an agent does whose
        audio is already buffered downstream.
        """
        if after_s <= 0:
            self._queue.clear()
            self._stop_now = True
        elif self._stop_at_s is None:
            self._stop_at_s = self.reply_played_s + after_s

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
            if self._stop_at_s is not None and self.reply_played_s >= self._stop_at_s:
                self._stop_at_s = None
                self.stop()
            if self._stop_now:
                return
            await self._send(to_pcm16(audio[offset : offset + FRAME_SAMPLES]))
            self.reply_played_s += FRAME_S
            delay = start + (n + 1) * FRAME_S - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
