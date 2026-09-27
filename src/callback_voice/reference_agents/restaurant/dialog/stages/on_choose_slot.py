import re

from callback_voice.reference_agents.restaurant.dialog.reply import Reply
from callback_voice.reference_agents.restaurant.dialog.stages.absorb_slots import absorb_slots
from callback_voice.reference_agents.restaurant.dialog.stages.ask_for_slot import ask_for_slot
from callback_voice.reference_agents.restaurant.dialog.turn_context import TurnContext


def on_choose_slot(ctx: TurnContext) -> Reply:
    """The caller picks one of the offered times, names another, or changes the day."""
    said, s = ctx.said, ctx.state
    text = said.text.lower()
    pick = None
    if s.offered and re.search(r"\b(second|later|latter|last)\b", text):
        pick = s.offered[-1]
    elif s.offered and (
        re.search(r"\b(first|earlier|former)\b", text)
        or (said.has("yes") and said.time is None and said.day is None)
    ):
        pick = s.offered[0]
    if pick is not None:
        s.hour, s.minute, s.earliest, s.latest = pick[0], pick[1], None, None
        return ask_for_slot(ctx)
    if said.time or said.day:
        absorb_slots(ctx)
        return ask_for_slot(ctx)
    if said.has("no"):
        s.stage = "new_time"
        return Reply("No problem. What other day or time would work?")
    s.misunderstood += 1
    return Reply("Sorry, which time would you like?")
