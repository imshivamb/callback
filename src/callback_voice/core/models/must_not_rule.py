import re

from pydantic import Field, field_validator

from callback_voice.core.models.strict_model import StrictModel


class MustNotRule(StrictModel):
    """Something the agent must never say, checked deterministically.

    ``says`` is a case-insensitive regular expression matched against each agent
    turn's transcript. Plain-text rules in ``must_not`` go to the LLM judge instead.
    """

    says: str = Field(min_length=1)
    why: str | None = None

    @field_validator("says")
    @classmethod
    def _compiles(cls, value: str) -> str:
        try:
            re.compile(value)
        except re.error as exc:
            raise ValueError(f"not a valid regular expression: {exc}") from exc
        return value

    @property
    def label(self) -> str:
        return self.why or f"says /{self.says}/"
