import re

from callback_voice.reference_agents.restaurant.dialog.reply import Reply
from callback_voice.reference_agents.restaurant.dialog.stages.absorb_slots import absorb_slots
from callback_voice.reference_agents.restaurant.dialog.stages.ask_for_slot import ask_for_slot
from callback_voice.reference_agents.restaurant.dialog.turn_context import TurnContext

_NAME = re.compile(
    r"(?:name is|it's|it is|under|this is|i'm|i am)\s+([A-Za-z][A-Za-z' -]{1,40})", re.I
)


def on_new_details(ctx: TurnContext) -> Reply:
    """Collect day, time, party size and name for a new booking, one gap at a time."""
    s = ctx.state
    absorb_slots(ctx)
    if s.stage == "new_name":
        match = _NAME.search(ctx.said.text)
        s.name = (match.group(1) if match else ctx.said.text).strip(" .,!?").title()
    s.stage = "new_details"
    if s.day is None or (s.hour is None and s.earliest is None):
        return Reply("Happy to book a table. What day and time would you like?")
    if s.party_size is None:
        return Reply("And how many people will be joining?")
    if s.name is None:
        s.stage = "new_name"
        return Reply("What name should I put the booking under?")
    return ask_for_slot(ctx)
