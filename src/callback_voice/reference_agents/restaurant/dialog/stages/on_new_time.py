from callback_voice.reference_agents.restaurant.dialog.reply import Reply
from callback_voice.reference_agents.restaurant.dialog.stages.absorb_slots import absorb_slots
from callback_voice.reference_agents.restaurant.dialog.stages.ask_for_slot import ask_for_slot
from callback_voice.reference_agents.restaurant.dialog.turn_context import TurnContext


def on_new_time(ctx: TurnContext) -> Reply:
    absorb_slots(ctx)
    if ctx.said.day is None and ctx.said.time is None:
        ctx.state.misunderstood += 1
        return Reply("Sorry, which day and time would suit you?")
    return ask_for_slot(ctx)
