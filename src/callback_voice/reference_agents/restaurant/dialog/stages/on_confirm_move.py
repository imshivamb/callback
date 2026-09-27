from callback_voice.reference_agents.restaurant.dialog.reply import Reply
from callback_voice.reference_agents.restaurant.dialog.speech_format import (
    say_day,
    say_phone,
    say_time,
)
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
    day, hour, minute = s.day or "", s.hour or 0, s.minute
    booking = ctx.store.find(ref)
    assert booking is not None
    party = s.party_size or booking.party_size
    if ctx.flaws.task_bug != "confirms_without_saving":  # bug: says "Done", saves nothing
        saved_hour = hour + 1 if ctx.flaws.task_bug == "wrong_hour" else hour  # bug: off by an hour
        ctx.store.move(ref, day, saved_hour, minute)
        ctx.store.update(ref, party_size=s.party_size, window_seat=s.window_seat or None)
    s.stage = "anything_else"
    window = ", and I've noted a window seat" if s.window_seat else ""
    return Reply(
        f"Done. Your table for {party} is now on {say_day(day)} at {say_time(hour, minute)}{window}. "
        f"Your reference is still {ctx.code(ref)}. I'll text a confirmation to {say_phone(booking.phone)}. "
        "Is there anything else I can help with?"
    )
