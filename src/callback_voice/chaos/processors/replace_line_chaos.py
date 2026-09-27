from callback_voice.caller.engine.utterance import UtteranceTag
from callback_voice.chaos.params.ask_for_human import AskForHumanParams
from callback_voice.chaos.params.change_mind import ChangeMindParams
from callback_voice.chaos.params.repeat_request import RepeatRequestParams
from callback_voice.chaos.processors.chaos_context import ChaosContext
from callback_voice.chaos.processors.chaos_processor import ChaosProcessor
from callback_voice.chaos.processors.line_plan import LinePlan
from callback_voice.core.models.chaos_event import ChaosEvent


class ReplaceLineChaos(ChaosProcessor):
    """Swaps the caller's line on the targeted turn: ask_for_human, repeat_request,
    change_mind. A changed mind also updates what the persona knows."""

    def __init__(self, event: ChaosEvent) -> None:
        params = event.params
        assert isinstance(params, AskForHumanParams | RepeatRequestParams | ChangeMindParams)
        self._event, self._say = event, params.say
        self._updates = params.updates if isinstance(params, ChangeMindParams) else {}
        self._tag: UtteranceTag = event.type  # type: ignore[assignment]

    def before_caller_turn(self, ctx: ChaosContext, turn: int, plan: LinePlan) -> LinePlan:
        if self._event.trigger is None or not self._event.trigger.matches_turn(turn):
            return plan
        ctx.note(self._event, ctx.t_s, caller_turn=turn, replaced=plan.text)
        plan.text, plan.tag = self._say, self._tag
        plan.chaos_id, plan.chaos_type = self._event.id, self._event.type
        plan.updates = {**plan.updates, **self._updates}
        plan.hang_up = False
        return plan
