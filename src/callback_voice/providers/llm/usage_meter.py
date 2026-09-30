from callback_voice.core.models.llm_usage import LlmUsage
from callback_voice.providers.llm.base import ChatMessage, ChatModel, Completion


class UsageMeter:
    """A ChatModel that counts every request and token passing through it.

    Wraps the caller's or the judge's model for one call, so results.json records
    what was actually used, not just the estimate printed before the run.
    """

    def __init__(self, llm: ChatModel) -> None:
        self._llm = llm
        self.name = llm.name
        self.model = llm.model
        self.usd_per_1k_tokens = llm.usd_per_1k_tokens
        self._requests = self._input = self._output = 0

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        seed: int | None = None,
        max_tokens: int = 400,
        json_mode: bool = False,
    ) -> Completion:
        completion = await self._llm.complete(
            messages, temperature=temperature, seed=seed, max_tokens=max_tokens, json_mode=json_mode
        )
        self._requests += 1
        self._input += completion.input_tokens
        self._output += completion.output_tokens
        return completion

    def usage(self) -> LlmUsage | None:
        """None when nothing was asked (a scripted or replayed caller)."""
        if not self._requests:
            return None
        return LlmUsage(
            model=self.model,
            requests=self._requests,
            input_tokens=self._input,
            output_tokens=self._output,
            usd=round((self._input + self._output) / 1000 * self.usd_per_1k_tokens, 6),
        )
