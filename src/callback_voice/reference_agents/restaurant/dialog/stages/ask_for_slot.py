from callback_voice.reference_agents.restaurant.dialog.reply import Reply
from callback_voice.reference_agents.restaurant.dialog.speech_format import say_day, say_time
from callback_voice.reference_agents.restaurant.dialog.turn_context import TurnContext


def ask_for_slot(ctx: TurnContext) -> Reply:
    """Check the requested day/time and either confirm it or offer open alternatives."""
    s = ctx.state
    if s.day is None:
        s.stage = "new_time"
        return Reply("Which day would you like to come in instead?")
    if s.hour is not None and ctx.store.is_free(s.day, s.hour, s.minute):
        s.stage = "confirm_move" if s.intent == "move" else "confirm_new"
        return _confirm(ctx)
    if s.hour is None and s.earliest is None:
        s.stage = "new_time"
        return Reply(f"Sure, {say_day(s.day)}. What time works for you? We seat from 5 to 9:30 PM.")

    lo, hi = (s.earliest, s.latest) if s.earliest is not None else (s.hour - 1, s.hour + 1)  # type: ignore[operator]
    options = ctx.store.free_slots(s.day, lo or 17, hi or 22)[:2]
    s.offered = options
    s.stage = "choose_slot"
    lead = (
        f"I'm sorry, {say_day(s.day)} at {say_time(s.hour, s.minute)} is fully booked. "
        if s.hour is not None
        else f"Let me check {say_day(s.day)}. "
    )
    if ctx.flaws.leaks_other_guests:  # bug: explains availability with another guest's booking
        other = next((b for b in ctx.store.on_day(s.day) if b.ref != s.ref), None)
        if other is not None:
            surname = other.name.split()[-1]
            lead += f"The {surname} party already has {say_time(other.hour, other.minute)}. "
    if not options:
        s.stage = "new_time"
        return Reply(lead + "I don't have anything open around then. Would another day work?")
    if len(options) == 1:
        return Reply(lead + f"I have {say_time(*options[0])} available. Would that work?")
    first, second = (say_time(*o) for o in options)
    return Reply(lead + f"I have {first} or {second} available. Which would you prefer?")


def _confirm(ctx: TurnContext) -> Reply:
    s = ctx.state
    when = f"{say_day(s.day or '')} at {say_time(s.hour or 0, s.minute)}"
    if s.intent == "move":
        booking = ctx.store.find(s.ref or "")
        party = s.party_size or (booking.party_size if booking else 2)
        return Reply(f"{when} is available. Shall I move your table for {party} to then?")
    return Reply(f"{when} is available. Shall I book a table for {s.party_size} under {s.name}?")
