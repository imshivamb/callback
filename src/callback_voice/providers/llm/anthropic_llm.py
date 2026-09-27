from typing import Any

from callback_voice.errors import ProviderError, ProviderUnavailableError
from callback_voice.providers.llm.base import ChatMessage, Completion

DEFAULT_MODEL = "claude-haiku-4-5"
_USD_PER_1K = {"claude-haiku-4-5": 0.003, "claude-sonnet-5": 0.006, "claude-opus-5": 0.015}


class AnthropicLlm:
    """Claude via the official ``anthropic`` SDK (opt-in extra).

    Credentials resolve the SDK's usual way (``ANTHROPIC_API_KEY`` or an
    ``ant auth login`` profile). Sampling parameters are only sent to models that
    accept them (Haiku); newer models reject ``temperature``.
    """

    name = "anthropic"

    def __init__(self, model: str = DEFAULT_MODEL, usd_per_1k_tokens: float | None = None) -> None:
        self.model = model
        self.usd_per_1k_tokens = usd_per_1k_tokens or _USD_PER_1K.get(model, 0.015)
        self._client: Any = None

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        seed: int | None = None,
        max_tokens: int = 400,
        json_mode: bool = False,
    ) -> Completion:
        import anthropic

        client = self._get_client()
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        if json_mode:
            system += "\n\nRespond with a single JSON object and nothing else."
        turns = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        extra: dict[str, Any] = {}
        if self.model.startswith("claude-haiku"):
            extra["temperature"] = temperature
        try:
            response = await client.messages.create(
                model=self.model, max_tokens=max_tokens, system=system, messages=turns, **extra
            )
        except anthropic.AuthenticationError as exc:
            raise ProviderError(
                "Anthropic rejected the credentials",
                hint="export ANTHROPIC_API_KEY=... or run `ant auth login`",
            ) from exc
        except anthropic.RateLimitError as exc:
            raise ProviderError("Anthropic rate limit hit", hint="lower `concurrency`") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"Anthropic returned {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError(f"cannot reach the Anthropic API: {exc}") from exc
        if response.stop_reason == "refusal":
            raise ProviderError("the model declined to play this persona")
        text = "".join(b.text for b in response.content if b.type == "text")
        return Completion(
            text, self.model, response.usage.input_tokens, response.usage.output_tokens
        )

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise ProviderUnavailableError(
                    "the anthropic SDK is not installed",
                    hint='pip install "callback-voice[anthropic]"',
                ) from exc
            self._client = anthropic.AsyncAnthropic()
        return self._client
