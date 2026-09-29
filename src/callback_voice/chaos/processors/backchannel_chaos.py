import numpy as np

from callback_voice.audio.format import Audio
from callback_voice.caller.speech.caller_speech import CallerSpeech
from callback_voice.chaos.params.backchannel import BackchannelParams
from callback_voice.chaos.processors.agent_turn_gate import AgentTurnGate
from callback_voice.chaos.processors.chaos_context import ChaosContext
from callback_voice.chaos.processors.chaos_processor import ChaosProcessor
from callback_voice.core.models.chaos_event import ChaosEvent


class BackchannelChaos(ChaosProcessor):
    """A short "mm-hmm" while the agent talks; the phrase is picked by the seeded RNG."""

    def __init__(self, event: ChaosEvent, rng: np.random.Generator) -> None:
        assert isinstance(event.params, BackchannelParams)
        self._event, self._params, self._rng = event, event.params, rng
        self._gate = AgentTurnGate(event)
        self._clips: list[Audio] = []

    async def prepare(self, speech: CallerSpeech) -> None:
        self._clips = [await speech.render(text) for text in self._params.say]

    def on_tick(self, ctx: ChaosContext) -> None:
        if self._gate.due(ctx):
            pick = int(self._rng.integers(len(self._clips)))
            ctx.interject(
                self._clips[pick],
                self._params.say[pick],
                "backchannel",
                self._event,
                self._gate.intended_s(ctx),
                self._gate.scheduled_s(ctx),
            )
