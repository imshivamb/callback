from dataclasses import dataclass, field
from typing import Final, Literal

from callback_voice.reference_agents.restaurant.dialog.agent_flaws import TaskBug

type BargeInPolicy = Literal["smart", "deaf_first_sentence"]


@dataclass(frozen=True, slots=True)
class AgentBehavior:
    """Everything that differs between the good agent and its buggy copy.

    Each field of ``BUGGY`` is a real-world voice-agent bug, chosen so that a
    specific Callback metric catches it.
    """

    name: str
    think_delay_s: float = 0.0
    """Extra delay before replying (a slow LLM). Caught by response latency."""
    end_of_turn_silence_s: float = 0.5
    """Caller silence that ends the caller's turn."""
    barge_in: BargeInPolicy = "smart"
    """smart: yield within ~0.4 s to real speech. deaf_first_sentence: the mic is
    muted while the first sentence of each reply plays (a common anti-echo hack),
    so early barge-ins are talked over. Caught by time-to-yield and talk-over."""
    filter_backchannels: bool = True
    """Keep talking through "mm-hmm". Without it the agent stops for any sound.
    Caught by false yield."""
    misread: dict[str, str] = field(default_factory=dict)
    """Characters garbled when reading codes aloud. Caught by entity fidelity."""
    task_bugs: tuple[TaskBug, ...] = ()
    """Task bugs this profile may have; one is picked per call (see pick_task_bug).
    Caught by task success."""
    leaks_other_guests: bool = False
    """Names another guest's booking when explaining availability. Caught by a
    ``must_not`` pattern rule."""
    reprompt_after_s: float | None = 5.0
    """Reprompt a silent caller. None never reprompts. Caught by silence handling."""
    voice: str = "af_heart"


GOOD: Final = AgentBehavior(name="good")
BUGGY: Final = AgentBehavior(
    name="buggy",
    think_delay_s=1.3,
    barge_in="deaf_first_sentence",
    filter_backchannels=False,
    misread={"D": "B"},
    task_bugs=("wrong_hour", "ignores_party_change", "confirms_without_saving"),
    leaks_other_guests=True,
    reprompt_after_s=None,
)
BEHAVIORS: Final = {b.name: b for b in (GOOD, BUGGY)}
