from callback_voice.caller.speech.caller_speech import CallerSpeech
from callback_voice.chaos.params.rate_change import RateChangeParams
from callback_voice.chaos.processors.chaos_context import ChaosContext
from callback_voice.chaos.processors.chaos_processor import ChaosProcessor
from callback_voice.chaos.processors.line_plan import LinePlan
from callback_voice.core.models.chaos_event import ChaosEvent


class RateChangeChaos(ChaosProcessor):
    """From the targeted caller turn on, the caller speaks at ``rate`` times their normal pace."""

    def __init__(self, event: ChaosEvent) -> None:
        assert isinstance(event.params, RateChangeParams)
        self._event, self._rate = event, event.params.rate
        self._speech: CallerSpeech | None = None
        self._base = 1.0

    async def prepare(self, speech: CallerSpeech) -> None:
        self._speech, self._base = speech, speech.rate

    def before_caller_turn(self, ctx: ChaosContext, turn: int, plan: LinePlan) -> LinePlan:
        if (
            self._speech is not None
            and self._event.trigger
            and self._event.trigger.matches_turn(turn)
        ):
            self._speech.rate = self._base * self._rate
            ctx.note(self._event, ctx.t_s, caller_turn=turn, rate=self._speech.rate)
        return plan
