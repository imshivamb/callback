import httpx

from callback_voice.errors import ProviderError
from callback_voice.providers.llm.base import ChatMessage, Completion

DEFAULT_URL = "http://localhost:11434"


class OllamaLlm:
    """A local model served by Ollama. Free."""

    name = "ollama"
    usd_per_1k_tokens = 0.0

    def __init__(self, model: str, base_url: str | None = None) -> None:
        self.model = model
        self._url = (base_url or DEFAULT_URL).rstrip("/")

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        seed: int | None = None,
        max_tokens: int = 400,
        json_mode: bool = False,
    ) -> Completion:
        body: dict[str, object] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "think": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                **({"seed": seed % 2**31} if seed is not None else {}),
            },
        }
        if json_mode:
            body["format"] = "json"
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(f"{self._url}/api/chat", json=body)
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Ollama at {self._url} is not reachable: {exc}",
                hint="run `ollama serve`, or use a scripted caller",
            ) from exc
        if response.status_code >= 400:
            raise ProviderError(
                f"Ollama returned {response.status_code}: {response.text[:200]}",
                hint=f"ollama pull {self.model}",
            )
        data = response.json()
        return Completion(
            data["message"]["content"],
            self.model,
            int(data.get("prompt_eval_count", 0)),
            int(data.get("eval_count", 0)),
        )
