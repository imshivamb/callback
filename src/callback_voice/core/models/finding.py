from typing import Literal

from callback_voice.core.models.strict_model import RecordModel


class Finding(RecordModel):
    """A located failure: the red pin on the report timeline.

    ``message`` is the one sentence shown when hovering the pin.
    """

    metric: str
    t_s: float
    end_s: float | None = None
    message: str
    severity: Literal["fail", "warn"] = "fail"
    chaos_id: str | None = None
