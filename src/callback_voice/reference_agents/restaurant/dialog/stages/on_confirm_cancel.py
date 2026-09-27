from callback_voice.reference_agents.restaurant.dialog.reply import Reply
from callback_voice.reference_agents.restaurant.dialog.turn_context import TurnContext


def on_confirm_cancel(ctx: TurnContext) -> Reply:
    said, s = ctx.said, ctx.state
    if said.has("yes") and not said.has("no"):
        ctx.store.cancel(s.ref or "")
        s.stage = "anything_else"
        return Reply("Your booking has been cancelled. Is there anything else I can help with?")
    s.stage = "anything_else"
    return Reply("Okay, I've left your booking as it is. Anything else I can help with?")
