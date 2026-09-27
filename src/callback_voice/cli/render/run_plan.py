from rich.text import Text

from callback_voice.core.runner.estimate_cost import CostEstimate


def run_plan(estimate: CostEstimate, llm_name: str, mode: str) -> Text:
    """The pre-run line: how many calls, how long at most, what it may cost."""
    cost = (
        "no LLM calls"
        if estimate.llm_calls == 0
        else (
            f"≈ ${estimate.usd:.2f} LLM ({llm_name})"
            if estimate.usd > 0
            else f"$0 LLM ({llm_name} free tier)"
        )
    )
    return Text.assemble(
        ("PLAN  ", "muted"),
        (f"{estimate.calls} call(s)", "bold"),
        (f" · up to {estimate.max_minutes:g} min · {cost} · caller {mode}", "muted"),
    )
