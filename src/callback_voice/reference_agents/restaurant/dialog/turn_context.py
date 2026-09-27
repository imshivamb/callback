from dataclasses import dataclass, field

from callback_voice.reference_agents.restaurant.bookings.booking_store import BookingStore
from callback_voice.reference_agents.restaurant.dialog.agent_flaws import AgentFlaws
from callback_voice.reference_agents.restaurant.dialog.dialog_state import DialogState
from callback_voice.reference_agents.restaurant.dialog.speech_format import say_code
from callback_voice.reference_agents.restaurant.dialog.utterance import Utterance


@dataclass(slots=True)
class TurnContext:
    """What a stage handler needs: the parsed turn, the state and the call's bookings."""

    said: Utterance
    state: DialogState
    store: BookingStore
    flaws: AgentFlaws = field(default_factory=AgentFlaws)

    def code(self, ref: str) -> str:
        return say_code(ref, misread=self.flaws.misread)
