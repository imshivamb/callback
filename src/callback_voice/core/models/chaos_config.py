from typing import Any

from pydantic import Field, model_validator

from callback_voice.chaos.params.noise import NoiseParams
from callback_voice.core.models.chaos_event import ChaosEvent
from callback_voice.core.models.strict_model import StrictModel


class ChaosConfig(StrictModel):
    """Everything that disrupts one scenario's calls."""

    noise: NoiseParams | None = None
    events: tuple[ChaosEvent, ...] = Field(default=())

    @model_validator(mode="before")
    @classmethod
    def _parse_events(cls, data: Any) -> Any:
        if not isinstance(data, dict) or "events" not in data:
            return data
        raw = data["events"] or []
        if not isinstance(raw, list):
            raise ValueError("chaos.events must be a list")
        events = [
            e if isinstance(e, ChaosEvent) else ChaosEvent.from_yaml(e, i)
            for i, e in enumerate(raw)
        ]
        return {**data, "events": events}

    @model_validator(mode="after")
    def _unique_ids(self) -> "ChaosConfig":
        ids = [e.id for e in self.events]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate chaos event ids: {', '.join(duplicates)}")
        return self
