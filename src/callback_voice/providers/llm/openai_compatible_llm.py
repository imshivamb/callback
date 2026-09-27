import os

import httpx

from callback_voice.errors import ProviderError
from callback_voice.providers.llm.base import ChatMessage, Completion


class OpenAiCompatibleLlm:
    """Any ``/chat/completions`` endpoint: OpenAI, Groq, Gemini's OpenAI API, OpenRouter,
    vLLM or LM Studio. Many offer free tiers suitable for the persona brain.
    """

    name = "openai-compatible"

    def __init__(
        self, model: str, base_url: str, api_key_env: str | None, usd_per_1k_tokens: float = 0.0
    ) -> None:
        self.model = model
        self.usd_per_1k_tokens = usd_per_1k_tokens
        self._url = base_url.rstrip("/")
        self._key_env = api_key_env

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        seed: int | None = None,
        max_tokens: int = 400,
        json_mode: bool = False,
    ) -> Completion:
        headers = {}
        if self._key_env:
            key = os.environ.get(self._key_env)
            if not key:
                raise ProviderError(
                    f"${self._key_env} is not set", hint=f"export {self._key_env}=..."
                )
            headers["Authorization"] = f"Bearer {key}"
        body: dict[str, object] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if seed is not None:
            body["seed"] = seed % 2**31
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self._url}/chat/completions", json=body, headers=headers
                )
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self._url} is not reachable: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderError(
                f"{self._url} returned {response.status_code}: {response.text[:200]}"
            )
        data = response.json()
        usage = data.get("usage") or {}
        return Completion(
            data["choices"][0]["message"]["content"] or "",
            self.model,
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
        )
