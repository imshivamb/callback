from callback_voice.audio.format import Audio
from callback_voice.caller.speech.caller_speech import CallerSpeech
from callback_voice.chaos.processors.chaos_context import ChaosContext
from callback_voice.chaos.processors.line_plan import LinePlan


class ChaosProcessor:
    """Base class: every hook is a no-op, each processor overrides what it needs.

    Hooks run on the call's tick loop, so they must be fast and must not await.
    Anything slow (rendering speech) happens in ``prepare`` before the call starts,
    which is what keeps chaos timing precise.
    """

    async def prepare(self, speech: CallerSpeech) -> None:
        """Pre-render audio this processor will need during the call."""

    def on_tick(self, ctx: ChaosContext) -> None:
        """Called once per 20 ms tick, before the caller's frame is produced."""

    def before_caller_turn(self, ctx: ChaosContext, turn: int, plan: LinePlan) -> LinePlan:
        """Rewrite the caller's ``turn``-th line (1-based) before it is rendered."""
        return plan

    def shape_outbound(self, ctx: ChaosContext, frame: Audio) -> Audio:
        """Transform the caller's outbound frame (noise, loss, jitter)."""
        return frame
