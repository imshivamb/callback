from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Reply:
    """What the agent says next. ``end_call`` hangs up after speaking."""

    text: str
    end_call: bool = False
