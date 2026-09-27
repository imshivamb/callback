from callback_voice.audio.dtmf import dtmf_tones
from callback_voice.chaos.params.dtmf import DtmfParams
from callback_voice.chaos.processors.chaos_context import ChaosContext
from callback_voice.chaos.processors.chaos_processor import ChaosProcessor
from callback_voice.chaos.processors.line_plan import LinePlan
from callback_voice.core.models.chaos_event import ChaosEvent


class DtmfChaos(ChaosProcessor):
    """Keypad tones: appended to a caller turn, or played at an absolute call time."""

    def __init__(self, event: ChaosEvent) -> None:
        assert isinstance(event.params, DtmfParams)
        self._event, self._digits = event, event.params.digits
        self._fired = False

    def before_caller_turn(self, ctx: ChaosContext, turn: int, plan: LinePlan) -> LinePlan:
        trigger = self._event.trigger
        if trigger is not None and trigger.on == "caller_turn" and trigger.matches_turn(turn):
            plan.dtmf = self._digits
            plan.chaos_id, plan.chaos_type = self._event.id, self._event.type
        return plan

    def on_tick(self, ctx: ChaosContext) -> None:
        trigger = self._event.trigger
        if self._fired or trigger is None or trigger.on != "time" or ctx.t_s < (trigger.at_s or 0):
            return
        self._fired = True
        ctx.interject(
            dtmf_tones(self._digits),
            f"[DTMF {self._digits}]",
            "dtmf",
            self._event,
            trigger.at_s or 0,
        )
