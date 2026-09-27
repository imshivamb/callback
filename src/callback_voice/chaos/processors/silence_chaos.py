from callback_voice.chaos.params.silence import SilenceParams
from callback_voice.chaos.processors.chaos_context import ChaosContext
from callback_voice.chaos.processors.chaos_processor import ChaosProcessor
from callback_voice.chaos.processors.line_plan import LinePlan
from callback_voice.core.models.chaos_event import ChaosEvent


class SilenceChaos(ChaosProcessor):
    """Instead of answering, the caller says nothing for ``duration_s``.

    If the agent reprompts during the silence, the caller answers after the reprompt.
    """

    def __init__(self, event: ChaosEvent) -> None:
        assert isinstance(event.params, SilenceParams)
        self._event, self._params = event, event.params

    def before_caller_turn(self, ctx: ChaosContext, turn: int, plan: LinePlan) -> LinePlan:
        if self._event.trigger is None or not self._event.trigger.matches_turn(turn):
            return plan
        ctx.note(self._event, ctx.t_s, duration_s=self._params.duration_s, caller_turn=turn)
        plan.lead_silence_s = self._params.duration_s
        plan.chaos_id, plan.chaos_type = self._event.id, self._event.type
        return plan
