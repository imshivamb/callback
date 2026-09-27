from pydantic import Field, model_validator

from callback_voice.chaos.params.base import ChaosParams


class PacketLossParams(ChaosParams):
    """Drop a share of the caller's outbound 20 ms frames inside a time window."""

    pct: float = Field(gt=0, le=100)
    from_s: float = Field(default=0.0, ge=0)
    to_s: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _window_is_ordered(self) -> "PacketLossParams":
        if self.to_s is not None and self.to_s <= self.from_s:
            raise ValueError("to_s must be after from_s")
        return self
