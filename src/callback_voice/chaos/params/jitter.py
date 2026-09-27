from pydantic import Field, model_validator

from callback_voice.chaos.params.base import ChaosParams


class JitterParams(ChaosParams):
    """Delay the caller's outbound frames by a random 0..``ms`` inside a window.

    Late frames are played out in order, so jitter stretches speech with small gaps,
    the way a jitter buffer under-run sounds on a bad line.
    """

    ms: float = Field(gt=0, le=1000)
    from_s: float = Field(default=0.0, ge=0)
    to_s: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _window_is_ordered(self) -> "JitterParams":
        if self.to_s is not None and self.to_s <= self.from_s:
            raise ValueError("to_s must be after from_s")
        return self
