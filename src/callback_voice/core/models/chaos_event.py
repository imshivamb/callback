from typing import Any

from pydantic import model_validator

from callback_voice.chaos.params.base import ChaosParams
from callback_voice.chaos.params.registry import PARAMS_BY_TYPE, ChaosType
from callback_voice.core.models.chaos_trigger import ChaosTrigger
from callback_voice.core.models.strict_model import StrictModel

_TRIGGER_KEYS = frozenset({"on", "turn", "every", "after_s", "at_s"})


class ChaosEvent(StrictModel):
    """One scheduled perturbation.

    Authored in YAML as a single-key mapping, e.g.
    ``- barge_in: {on: agent_turn, turn: 2, after_s: 0.8, say: "haan haan"}``.
    Trigger keys and parameter keys share that mapping and are split here.
    """

    id: str
    type: ChaosType
    trigger: ChaosTrigger | None
    params: ChaosParams

    @classmethod
    def from_yaml(cls, item: object, index: int) -> "ChaosEvent":
        """Build an event from its YAML form; ``index`` makes the default id unique."""
        if not isinstance(item, dict) or len(item) != 1:
            raise ValueError("each chaos event is a single-key mapping like '- barge_in: {...}'")
        [(type_name, body)] = item.items()
        body = dict(body or {})
        event_id = str(body.pop("id", f"{type_name}-{index + 1}"))
        trigger = {k: body.pop(k) for k in list(body) if k in _TRIGGER_KEYS}
        return cls.model_validate(
            {"id": event_id, "type": type_name, "trigger": trigger or None, "params": body}
        )

    @model_validator(mode="before")
    @classmethod
    def _typed_params(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        type_name = data.get("type")
        params_model = PARAMS_BY_TYPE.get(str(type_name))
        if params_model is None:
            known = ", ".join(sorted(PARAMS_BY_TYPE))
            raise ValueError(f"unknown chaos event {type_name!r}; known events: {known}")
        params = data.get("params")
        if not isinstance(params, ChaosParams):
            data = {**data, "params": params_model.model_validate(params or {})}
        return data

    @model_validator(mode="after")
    def _trigger_allowed(self) -> "ChaosEvent":
        allowed = type(self.params).triggers
        if not allowed and self.trigger is not None:
            raise ValueError(f"{self.type} is a window/continuous effect and takes no trigger")
        if allowed and self.trigger is None:
            raise ValueError(f"{self.type} needs a trigger: on: {' | '.join(allowed)}")
        if self.trigger is not None and self.trigger.on not in allowed:
            raise ValueError(f"{self.type} cannot trigger on {self.trigger.on}")
        return self

    @property
    def after_s(self) -> float:
        """Offset into the agent turn, falling back to the event type's default."""
        if self.trigger is not None and self.trigger.after_s is not None:
            return self.trigger.after_s
        return type(self.params).default_after_s or 0.0
