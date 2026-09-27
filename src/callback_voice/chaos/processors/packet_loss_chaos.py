import numpy as np

from callback_voice.audio.format import Audio
from callback_voice.chaos.params.packet_loss import PacketLossParams
from callback_voice.chaos.processors.chaos_context import ChaosContext
from callback_voice.chaos.processors.chaos_processor import ChaosProcessor
from callback_voice.core.models.chaos_event import ChaosEvent


class PacketLossChaos(ChaosProcessor):
    """Drops a seeded ``pct`` of the caller's 20 ms frames inside the window (silence, no concealment)."""

    def __init__(self, event: ChaosEvent, rng: np.random.Generator) -> None:
        assert isinstance(event.params, PacketLossParams)
        self._event, self._p, self._rng = event, event.params, rng
        self._dropped = 0
        self._state = "before"

    def shape_outbound(self, ctx: ChaosContext, frame: Audio) -> Audio:
        inside = ctx.t_s >= self._p.from_s and (self._p.to_s is None or ctx.t_s < self._p.to_s)
        if inside and self._state == "before":
            self._state = "inside"
            ctx.note(self._event, ctx.t_s, pct=self._p.pct, phase="start")
        elif not inside and self._state == "inside":
            self._state = "after"
            ctx.note(self._event, ctx.t_s, phase="end", frames_dropped=self._dropped)
        if inside and self._rng.random() < self._p.pct / 100:
            self._dropped += 1
            return np.zeros_like(frame)
        return frame
