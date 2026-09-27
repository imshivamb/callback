from typing import Any, Literal

from pydantic import model_validator

from callback_voice.core.models.strict_model import StrictModel

type FactKind = Literal["code", "count", "time", "phone", "text"]
_KINDS = ("code", "count", "time", "phone", "text")


class ExpectedFact(StrictModel):
    """A fact the agent must say correctly, checked on the agent's own audio.

    YAML forms: ``DX7Q2`` (a code or phrase), ``{code: DX7Q2}``, ``{count: 5, of: people}``,
    ``{time: "7:30 PM"}``, ``{phone: "98100 12345"}``, ``{text: Saturday}``. Add
    ``label`` to name it in results ("party size").
    """

    kind: FactKind
    value: str
    of: str = "people"
    label: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _from_yaml(cls, data: Any) -> Any:
        if isinstance(data, str):
            is_code = any(c.isdigit() for c in data) or (data.isupper() and len(data) <= 8)
            return {"kind": "code" if is_code else "text", "value": data}
        if isinstance(data, dict) and "kind" not in data:
            kinds = [k for k in _KINDS if k in data]
            if len(kinds) != 1:
                raise ValueError(f"a fact needs exactly one of {', '.join(_KINDS)}")
            rest = {k: v for k, v in data.items() if k != kinds[0]}
            return {"kind": kinds[0], "value": str(data[kinds[0]]), **rest}
        return data

    @property
    def name(self) -> str:
        return self.label or f"{self.kind} {self.value}"
