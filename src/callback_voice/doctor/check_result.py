from dataclasses import dataclass
from typing import Literal

type CheckStatus = Literal["ok", "warn", "fail", "skip"]


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Outcome of one environment check.

    ``fail`` means Callback cannot run at all; ``warn`` means an optional path
    (local models, a hosted provider, a target) is not ready.
    """

    group: str
    name: str
    status: CheckStatus
    detail: str
    fix: str | None = None
