from dataclasses import dataclass, field

from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric


@dataclass(frozen=True, slots=True)
class MetricResult:
    metrics: list[Metric]
    findings: list[Finding] = field(default_factory=list)
