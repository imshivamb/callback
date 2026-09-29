from callback_voice.chaos.processors.chaos_context import ChaosContext
from callback_voice.core.models.chaos_event import ChaosEvent


class AgentTurnGate:
    """Decides the tick at which an agent-turn event fires: once per matching turn,
    ``after_s`` into it, while the agent is actually speaking and the caller is not."""

    def __init__(self, event: ChaosEvent) -> None:
        self._event = event
        self._done: set[int] = set()

    def due(self, ctx: ChaosContext) -> bool:
        trigger, turn = self._event.trigger, ctx.agent_turn
        if (
            trigger is None
            or turn in self._done
            or not ctx.agent_in_turn
            or not trigger.matches_turn(turn)
        ):
            return False
        if (
            ctx.elapsed_in_agent_turn < self._event.after_s
            or not ctx.agent_speaking
            or ctx.caller_speaking
        ):
            return False
        self._done.add(turn)
        return True

    def scheduled_s(self, ctx: ChaosContext) -> float:
        """When the scenario asked for it: ``after_s`` into the agent's turn."""
        return ctx.agent_turn_start_s + self._event.after_s

    def intended_s(self, ctx: ChaosContext) -> float:
        """When the rule allowed it: the schedule, or later if it had to wait for the
        agent to be speaking and the caller to be quiet. Chaos drift is measured from
        here, so it shows the caller falling behind, not the rule waiting."""
        return max(self.scheduled_s(ctx), ctx.t_s)
