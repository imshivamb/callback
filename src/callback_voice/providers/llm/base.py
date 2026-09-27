from dataclasses import dataclass
from typing import Literal, Protocol

type Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Role
    content: str


@dataclass(frozen=True, slots=True)
class Completion:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class ChatModel(Protocol):
    """A chat LLM used for the persona brain and the judge.

    ``seed`` is passed where the backend supports it; replay additionally forces
    ``temperature=0`` so sampling is as reproducible as the backend allows.
    """

    name: str
    model: str
    usd_per_1k_tokens: float

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        seed: int | None = None,
        max_tokens: int = 400,
        json_mode: bool = False,
    ) -> Completion: ...
