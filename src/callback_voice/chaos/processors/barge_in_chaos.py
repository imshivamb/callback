import numpy as np

from callback_voice.audio.format import Audio
from callback_voice.caller.speech.caller_speech import CallerSpeech
from callback_voice.chaos.params.barge_in import BargeInParams
from callback_voice.chaos.processors.agent_turn_gate import AgentTurnGate
from callback_voice.chaos.processors.chaos_context import ChaosContext
from callback_voice.chaos.processors.chaos_processor import ChaosProcessor
from callback_voice.core.models.chaos_event import ChaosEvent


class BargeInChaos(ChaosProcessor):
    """The caller talks over the agent ``after_s`` into the targeted agent turn."""

    def __init__(self, event: ChaosEvent) -> None:
        assert isinstance(event.params, BargeInParams)
        self._event, self._params = event, event.params
        self._gate = AgentTurnGate(event)
        self._audio: Audio = np.zeros(0, np.float32)

    async def prepare(self, speech: CallerSpeech) -> None:
        self._audio = await speech.render(self._params.say)

    def on_tick(self, ctx: ChaosContext) -> None:
        if self._gate.due(ctx):
            ctx.interject(
                self._audio, self._params.say, "barge_in", self._event, self._gate.intended_s(ctx)
            )
