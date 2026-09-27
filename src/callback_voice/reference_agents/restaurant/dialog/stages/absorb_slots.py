from callback_voice.reference_agents.restaurant.dialog.turn_context import TurnContext


def absorb_slots(ctx: TurnContext) -> None:
    """Copy any day, time or party size in this turn into the dialog state.

    Before the booking is found, a time equal to its current time is ignored: "my Friday
    8 PM table" names the old slot, not the new one.
    """
    said, s = ctx.said, ctx.state
    if said.day:
        s.day = said.day
    if said.party_size:
        s.party_size = said.party_size
    if said.has("window"):
        s.window_seat = True
    if said.time is None:
        return
    booking = ctx.store.find(s.ref) if s.ref else None
    if said.time.is_range:
        s.earliest, s.latest, s.hour = said.time.earliest, said.time.latest, None
        return
    if (
        booking
        and s.intent == "move"
        and s.stage in {"intent", "ref"}
        and (said.time.hour, said.time.minute) == (booking.hour, booking.minute)
    ):
        return
    s.hour, s.minute, s.earliest, s.latest = said.time.hour, said.time.minute, None, None
