from callback_voice.reference_agents.restaurant.dialog.reply import Reply
from callback_voice.reference_agents.restaurant.dialog.speech_format import say_day, say_time
from callback_voice.reference_agents.restaurant.dialog.turn_context import TurnContext

NEW_BOOKING_REF = "HN3W5"


def on_confirm_new(ctx: TurnContext) -> Reply:
    said, s = ctx.said, ctx.state
    if not said.has("yes") or said.has("no"):
        s.stage = "new_details"
        s.hour = None
        return Reply("No problem. What time would you prefer instead?")
    booking = ctx.store.create(
        NEW_BOOKING_REF, s.name or "Guest", s.day or "", s.hour or 0, s.minute, s.party_size or 2
    )
    s.ref = booking.ref
    s.stage = "anything_else"
    return Reply(
        f"You're booked: a table for {booking.party_size} on {say_day(booking.day)} at "
        f"{say_time(booking.hour, booking.minute)}. Your reference is {ctx.code(booking.ref)}. "
        "Anything else I can help with?"
    )
