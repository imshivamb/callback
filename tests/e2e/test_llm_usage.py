"""What the caller and judge LLMs actually used is recorded, not only estimated."""

from callback_voice.cli.render.usage_line import usage_line
from callback_voice.core.models.llm_usage import LlmUsage
from callback_voice.providers.llm.base import ChatMessage, Completion
from callback_voice.providers.llm.usage_meter import UsageMeter


class FakeLlm:
    name = "fake"
    model = "fake-model-1"
    usd_per_1k_tokens = 0.002

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        seed: int | None = None,
        max_tokens: int = 400,
        json_mode: bool = False,
    ) -> Completion:
        return Completion('{"say": "hi"}', self.model, input_tokens=1200, output_tokens=30)


async def test_meter_counts_requests_tokens_and_cost() -> None:
    meter = UsageMeter(FakeLlm())
    assert meter.usage() is None  # nothing asked yet: a scripted or replayed caller
    for _ in range(3):
        await meter.complete([ChatMessage("user", "hello")])
    usage = meter.usage()
    assert usage is not None
    assert (usage.model, usage.requests, usage.input_tokens, usage.output_tokens) == (
        "fake-model-1",
        3,
        3600,
        90,
    )
    assert usage.usd == round(3690 / 1000 * 0.002, 6)


def test_run_totals_add_up_and_are_printed() -> None:
    one = LlmUsage(model="m", requests=6, input_tokens=8000, output_tokens=200, usd=0.0)
    total = one + one
    assert (total.requests, total.input_tokens, total.output_tokens) == (12, 16000, 400)
    line = usage_line({"caller": total})
    assert line is not None
    assert "caller m: 12 request(s), 16,000 in + 400 out tokens ≈ $0.00" in line.plain
    assert usage_line({}) is None
