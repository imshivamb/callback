from callback_voice.reference_agents.restaurant.dialog.reply import Reply
from callback_voice.reference_agents.restaurant.dialog.stages.absorb_slots import absorb_slots
from callback_voice.reference_agents.restaurant.dialog.stages.on_new_details import on_new_details
from callback_voice.reference_agents.restaurant.dialog.stages.on_ref import on_ref
from callback_voice.reference_agents.restaurant.dialog.turn_context import TurnContext


def on_intent(ctx: TurnContext) -> Reply:
    """Work out what the caller wants, keeping any details they already gave."""
    said, s = ctx.said, ctx.state
    absorb_slots(ctx)
    if said.has("move") or said.has("cancel") or said.has("check"):
        s.intent = (
            "cancel"
            if said.has("cancel")
            else "check"
            if said.has("check") and not said.has("move")
            else "move"
        )
        if said.code:
            return on_ref(ctx)
        s.stage = "ref"
        verb = {"move": "move your booking", "cancel": "cancel that", "check": "check that"}[
            s.intent
        ]
        return Reply(
            f"Sure, I can help {verb}. What's the booking reference? "
            "It's the five-character code in your confirmation."
        )
    if said.has("new") or (said.day and (said.time or said.party_size)):
        s.intent = "new"
        return on_new_details(ctx)
    if said.code:
        s.intent = "move"
        return on_ref(ctx)
    s.misunderstood += 1
    return Reply(
        "Sorry, I didn't quite get that. Are you looking to make a new booking, "
        "or change an existing one?"
    )
