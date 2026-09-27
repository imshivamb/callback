from callback_voice.reference_agents.restaurant.dialog.reply import Reply
from callback_voice.reference_agents.restaurant.dialog.speech_format import say_day, say_time
from callback_voice.reference_agents.restaurant.dialog.turn_context import TurnContext


def on_confirm_move(ctx: TurnContext) -> Reply:
    said, s = ctx.said, ctx.state
    if said.has("no") and not said.has("yes"):
        s.stage = "new_time"
        return Reply("No problem. What day and time would you prefer?")
    if not said.has("yes"):
        s.misunderstood += 1
        return Reply("Sorry, shall I go ahead and move it? Yes or no?")
    ref = s.ref or ""
    booking = ctx.store.move(ref, s.day or "", s.hour or 0, s.minute)
    ctx.store.update(ref, party_size=s.party_size, window_seat=s.window_seat or None)
    s.stage = "anything_else"
    window = ", and I've noted a window seat" if booking.window_seat else ""
    return Reply(
        f"Done. Your table for {booking.party_size} is now on {say_day(booking.day)} at "
        f"{say_time(booking.hour, booking.minute)}{window}. Your reference is still "
        f"{ctx.code(ref)}. Is there anything else I can help with?"
    )
