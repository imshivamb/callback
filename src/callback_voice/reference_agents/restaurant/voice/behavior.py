from dataclasses import dataclass, field
from typing import Final, Literal

from callback_voice.reference_agents.restaurant.dialog.agent_flaws import TaskBug

type BargeInPolicy = Literal["smart", "deaf_opening", "ignore"]


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
    """smart: yield within ~0.4 s to real speech. deaf_opening: the mic is muted for
    the first ``deaf_opening_s`` of each reply's audio (a common anti-echo hack with a
    fixed window), so early barge-ins are talked over. Caught by time-to-yield and
    talk-over. ignore: never yields and never answers anything said over it, as if the caller had
    not spoken (per call: ``?barge_in=ignore`` on the URL). Caught by time-to-yield and
    unanswered turns."""
    deaf_opening_s: float = 0.0
    """How much of each reply's audio plays with the mic muted (``deaf_opening`` only).
    Counted in audio played, so a slow machine doesn't change it."""
    stop_lag_s: float = 0.0
    """Audio that keeps playing after the agent decides to stop, as if it had already
    been sent downstream. Caught by time-to-yield."""
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
    synthesis_delay_s: float = 0.0
    """Extra wait before synthesising each part of a reply: simulates a slow machine,
    whose pauses mid-reply a caller can mistake for the end of the agent's turn."""
    voice: str = "af_heart"


GOOD: Final = AgentBehavior(name="good")
BUGGY: Final = AgentBehavior(
    name="buggy",
    think_delay_s=1.3,
    # Muted for 1.8 s: long enough to talk over an early barge-in, short enough that a
    # "mm-hmm" 2 s into a reply is still heard (and wrongly stopped for, within 1 s even
    # with the 0.6 s lag, so the false-yield bug stays visible).
    barge_in="deaf_opening",
    deaf_opening_s=1.8,
    stop_lag_s=0.6,
    filter_backchannels=False,
    misread={"D": "B"},
    task_bugs=("wrong_hour", "ignores_party_change", "confirms_without_saving"),
    leaks_other_guests=True,
    reprompt_after_s=None,
)
BEHAVIORS: Final = {b.name: b for b in (GOOD, BUGGY)}
