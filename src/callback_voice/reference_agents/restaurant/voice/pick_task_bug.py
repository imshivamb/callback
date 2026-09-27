from callback_voice.core.seeds.derive_seed import derive_seed
from callback_voice.reference_agents.restaurant.dialog.agent_flaws import TASK_BUGS, TaskBug
from callback_voice.reference_agents.restaurant.voice.behavior import AgentBehavior


def pick_task_bug(behavior: AgentBehavior, call_id: str, requested: str | None) -> TaskBug | None:
    """The task bug active for one call.

    A ``?task_bug=<name>`` on the connection URL forces one (``none`` disables it).
    Otherwise a profile with task bugs picks one from a seed on the call id, so the
    same call id always gets the same bug and different trials get different ones.
    """
    if requested is not None:
        if requested == "none":
            return None
        if requested not in TASK_BUGS:
            raise ValueError(f"unknown task_bug {requested!r}; known: {', '.join(TASK_BUGS)}")
        return requested  # type: ignore[return-value]
    if not behavior.task_bugs:
        return None
    return behavior.task_bugs[derive_seed("task_bug", call_id) % len(behavior.task_bugs)]
