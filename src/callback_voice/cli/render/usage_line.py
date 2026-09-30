from rich.text import Text

from callback_voice.core.models.llm_usage import LlmUsage


def usage_line(usage: dict[str, LlmUsage]) -> Text | None:
    """What the LLMs actually used in the run, next to the estimate printed before it."""
    if not usage:
        return None
    parts = [
        f"{role} {u.model}: {u.requests} request(s), {u.input_tokens:,} in + "
        f"{u.output_tokens:,} out tokens ≈ ${u.usd:.2f}"
        for role, u in usage.items()
    ]
    return Text("LLM used  " + " · ".join(parts) + " (at the configured price)\n", style="muted")
