from callback_voice.core.models.metric import Comparator, MetricMethod
from callback_voice.core.models.strict_model import RecordModel


class Aggregate(RecordModel):
    """A metric summarised across trials with a 95% interval.

    Rates use a Wilson interval; latencies use a seeded bootstrap.
    """

    name: str
    value: float | None
    ci_low: float | None
    ci_high: float | None
    n: int
    unit: str
    method: MetricMethod
    threshold: float | None = None
    comparator: Comparator = "<="
    passed: bool | None = None
