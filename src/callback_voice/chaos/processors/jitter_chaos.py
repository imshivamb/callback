from collections import deque

import numpy as np

from callback_voice.audio.format import FRAME_MS, Audio
from callback_voice.chaos.params.jitter import JitterParams
from callback_voice.chaos.processors.chaos_context import ChaosContext
from callback_voice.chaos.processors.chaos_processor import ChaosProcessor
from callback_voice.core.models.chaos_event import ChaosEvent

_SILENT_RMS = 1e-4


class JitterChaos(ChaosProcessor):
    """Delays the caller's frames by a seeded 0..``ms`` inside the window, keeping order.

    Late frames leave gaps and the backlog plays out afterwards; once the window
    ends, silent frames are dropped until the line has caught up, the way a jitter
    buffer drains.
    """

    def __init__(self, event: ChaosEvent, rng: np.random.Generator) -> None:
        assert isinstance(event.params, JitterParams)
        self._event, self._p, self._rng = event, event.params, rng
        self._queue: deque[tuple[int, Audio]] = deque()
        self._last_release = -1
        self._noted = False

    def shape_outbound(self, ctx: ChaosContext, frame: Audio) -> Audio:
        inside = ctx.t_s >= self._p.from_s and (self._p.to_s is None or ctx.t_s < self._p.to_s)
        if inside and not self._noted:
            self._noted = True
            ctx.note(self._event, ctx.t_s, ms=self._p.ms)
        if not inside and not self._queue:
            return frame
        catching_up = not inside and float(np.sqrt(np.mean(frame**2))) < _SILENT_RMS
        if not catching_up:
            delay = int(self._rng.integers(0, int(self._p.ms // FRAME_MS) + 1)) if inside else 0
            release = max(self._last_release + 1, ctx.tick + delay)
            self._queue.append((release, frame))
            self._last_release = release
        if self._queue and self._queue[0][0] <= ctx.tick:
            return self._queue.popleft()[1]
        return np.zeros_like(frame)
