import asyncio
import time

from callback_voice.audio.format import FRAME_S


class TickClock:
    """Absolute 20 ms schedule: tick ``n`` is due at ``start + n * 20 ms``.

    Sleeping to absolute deadlines means a slow tick never accumulates drift; it is
    measured instead (``max_lateness_s``) and reported when it could skew chaos
    timing.
    """

    def __init__(self) -> None:
        self.tick = 0
        self._start = 0.0
        self.max_lateness_s = 0.0

    def start(self) -> None:
        self._start = time.monotonic()
        self.tick = 0

    @property
    def t_s(self) -> float:
        """Call time of the current tick on the recording clock."""
        return self.tick * FRAME_S

    async def next(self) -> None:
        self.tick += 1
        due = self._start + self.tick * FRAME_S
        now = time.monotonic()
        if due > now:
            await asyncio.sleep(due - now)
        else:
            self.max_lateness_s = max(self.max_lateness_s, now - due)
