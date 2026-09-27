from dataclasses import dataclass, field
from typing import Final, Literal, get_args

type TaskBug = Literal["wrong_hour", "ignores_party_change", "confirms_without_saving"]
TASK_BUGS: Final[tuple[str, ...]] = get_args(TaskBug.__value__)


@dataclass(frozen=True, slots=True)
class AgentFlaws:
    """Deliberate content bugs the dialog can have for one call. All off by default.

    ``task_bug`` is at most one task bug per call:

    - ``wrong_hour``: says the time the caller chose, saves one hour later.
    - ``ignores_party_change``: says "updated to N people", keeps the old size.
    - ``confirms_without_saving``: says "Done", saves nothing.

    ``leaks_other_guests`` names another guest's booking when explaining availability
    (a privacy bug). ``misread`` garbles characters when reading codes aloud.
    """

    misread: dict[str, str] = field(default_factory=dict)
    task_bug: TaskBug | None = None
    leaks_other_guests: bool = False
