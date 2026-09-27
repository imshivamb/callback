from callback_voice.reference_agents.restaurant.dialog.reply import Reply
from callback_voice.reference_agents.restaurant.dialog.speech_format import say_day, say_time
from callback_voice.reference_agents.restaurant.dialog.stages.ask_for_slot import ask_for_slot
from callback_voice.reference_agents.restaurant.dialog.turn_context import TurnContext


def on_ref(ctx: TurnContext) -> Reply:
    """Look up the booking reference and move on to what the caller asked for."""
    said, s = ctx.said, ctx.state
    if said.code is None:
        s.misunderstood += 1
        return Reply(
            "Sorry, I didn't catch the reference. Could you read it out one character at a time?"
        )
    booking = ctx.store.find(said.code)
    if booking is None:
        s.misunderstood += 1
        return Reply(
            f"I couldn't find a booking with the reference {ctx.code(said.code)}. "
            "Could you check it and read it again?"
        )
    s.ref = booking.ref
    first_name = booking.name.split()[0]
    found = (
        f"Thanks, {first_name}. I've found your booking, reference {ctx.code(booking.ref)}: "
        f"a table for {booking.party_size} on {say_day(booking.day)} at "
        f"{say_time(booking.hour, booking.minute)}."
    )
    if s.intent == "cancel":
        s.stage = "confirm_cancel"
        return Reply(f"{found} Would you like me to cancel it?")
    if s.intent == "check":
        s.stage = "anything_else"
        return Reply(f"{found} Is there anything else I can help with?")
    if (s.day and s.day != booking.day) or s.hour is not None or s.earliest is not None:
        return Reply(f"{found} {ask_for_slot(ctx).text}")
    s.stage = "new_time"
    return Reply(f"{found} What day and time would you like instead?")
