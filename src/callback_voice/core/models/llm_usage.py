from callback_voice.core.models.strict_model import RecordModel


class LlmUsage(RecordModel):
    """What an LLM was actually asked for during a call or a run.

    ``usd`` is the tokens times the configured ``usd_per_1k_tokens`` (0 for a
    free-tier configuration), so it is only as accurate as that price.
    """

    model: str
    requests: int
    input_tokens: int
    output_tokens: int
    usd: float

    def __add__(self, other: "LlmUsage") -> "LlmUsage":
        return LlmUsage(
            model=self.model if self.model == other.model else f"{self.model}, {other.model}",
            requests=self.requests + other.requests,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            usd=round(self.usd + other.usd, 6),
        )
