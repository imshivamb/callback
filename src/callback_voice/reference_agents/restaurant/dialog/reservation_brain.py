from collections.abc import Callable
from typing import Final

from callback_voice.reference_agents.restaurant.bookings.booking_store import (
    MAX_PARTY,
    BookingStore,
)
from callback_voice.reference_agents.restaurant.dialog.dialog_state import DialogState, Stage
from callback_voice.reference_agents.restaurant.dialog.reply import Reply
from callback_voice.reference_agents.restaurant.dialog.stages.ask_for_slot import ask_for_slot
from callback_voice.reference_agents.restaurant.dialog.stages.on_choose_slot import on_choose_slot
from callback_voice.reference_agents.restaurant.dialog.stages.on_confirm_cancel import (
    on_confirm_cancel,
)
from callback_voice.reference_agents.restaurant.dialog.stages.on_confirm_move import on_confirm_move
from callback_voice.reference_agents.restaurant.dialog.stages.on_confirm_new import on_confirm_new
from callback_voice.reference_agents.restaurant.dialog.stages.on_intent import on_intent
from callback_voice.reference_agents.restaurant.dialog.stages.on_new_details import on_new_details
from callback_voice.reference_agents.restaurant.dialog.stages.on_new_time import on_new_time
from callback_voice.reference_agents.restaurant.dialog.stages.on_ref import on_ref
from callback_voice.reference_agents.restaurant.dialog.turn_context import TurnContext
from callback_voice.reference_agents.restaurant.dialog.utterance import understand

GREETING: Final = (
    "Thanks for calling Olive and Ember. I'm Ava, the reservations assistant. "
    "How can I help you today?"
)
REPROMPT: Final = (
    "Are you still there? I can help with a new booking or a change to an existing one."
)
_GIVE_UP_AFTER = 4

_HANDLERS: Final[dict[Stage, Callable[[TurnContext], Reply]]] = {
    "intent": on_intent,
    "ref": on_ref,
    "new_time": on_new_time,
    "choose_slot": on_choose_slot,
    "confirm_move": on_confirm_move,
    "confirm_cancel": on_confirm_cancel,
    "new_details": on_new_details,
    "new_name": on_new_details,
    "confirm_new": on_confirm_new,
}


class ReservationBrain:
    """Deterministic dialog manager for one call: text in, reply out.

    Rule-based on purpose. A reference agent must behave identically on every run
    so that Callback's own CI can assert exact outcomes against it.
    """

    def __init__(self, store: BookingStore, *, misread: dict[str, str] | None = None) -> None:
        self.store = store
        self.state = DialogState()
        self._misread = misread or {}

    def greet(self) -> Reply:
        return self._remember(Reply(GREETING))

    def reprompt(self) -> Reply:
        return Reply(REPROMPT)

    def respond(self, text: str) -> Reply:
        s = self.state
        said = understand(
            text, expecting_time=s.stage in {"new_time", "choose_slot", "new_details"}
        )
        ctx = TurnContext(said, s, self.store, self._misread)

        if said.has("repeat") and s.last_reply:
            return Reply(f"Of course. {s.last_reply}")
        if said.has("human"):
            return self._remember(
                Reply(
                    "I understand. I'm an automated assistant, and I can transfer you to the team if "
                    "you'd like. I can also sort this out for you right now. What would you prefer?"
                )
            )
        if (said.has("goodbye") and s.stage != "confirm_move") or (
            s.stage == "anything_else" and said.has("no")
        ):
            s.stage = "done"
            return Reply(
                "You're all set. Thanks for calling Olive and Ember, and have a lovely evening. Goodbye!",
                end_call=True,
            )

        prefix = self._party_change(ctx)
        if s.stage == "anything_else":
            s.stage = "intent"
        if prefix and s.stage in {"confirm_move", "confirm_new"} and not said.has("yes"):
            reply = ask_for_slot(ctx)  # re-confirm with the new party size
        else:
            reply = _HANDLERS.get(s.stage, on_intent)(ctx)
        if s.misunderstood >= _GIVE_UP_AFTER:
            return Reply(
                "I'm sorry, I'm having trouble understanding. I'll pass you to a team member "
                "who can help. Goodbye.",
                end_call=True,
            )
        return self._remember(Reply(f"{prefix}{reply.text}".strip(), reply.end_call))

    def _party_change(self, ctx: TurnContext) -> str:
        """Handle "actually make it 5 people" at any point, including after the move."""
        size, s = ctx.said.party_size, ctx.state
        if size is None or size == s.party_size:
            return ""
        if size > MAX_PARTY:
            return f"For groups over {MAX_PARTY}, our events team will need to help. "
        s.party_size = size
        booking = ctx.store.find(s.ref) if s.ref else None
        if booking is not None and booking.status == "moved" and booking.party_size != size:
            ctx.store.update(booking.ref, party_size=size)
            return f"No problem, I've updated your booking to {size} people. "
        return f"Got it, {size} people. " if s.stage not in {"intent", "new_details"} else ""

    def _remember(self, reply: Reply) -> Reply:
        self.state.last_reply = reply.text
        return reply
