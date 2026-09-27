from rich.text import Text

from callback_voice.core.runner.estimate_cost import CostEstimate


def run_plan(estimate: CostEstimate, llm_name: str, judge_name: str | None, mode: str) -> Text:
    """The pre-run line: how many calls, how long at most, which LLM calls, what it may cost."""
    uses = []
    if estimate.llm_calls:
        uses.append(f"caller LLM ({llm_name}) ×{estimate.llm_calls}")
    if estimate.judge_calls:
        uses.append(f"judge ({judge_name}) ×{estimate.judge_calls}")
    if not uses:
        cost = "no LLM calls"
    elif estimate.usd > 0:
        cost = f"{', '.join(uses)} ≈ ${estimate.usd:.2f}"
    else:
        cost = f"{', '.join(uses)} · $0 (free tier)"
    return Text.assemble(
        ("PLAN  ", "muted"),
        (f"{estimate.calls} call(s)", "bold"),
        (f" · up to {estimate.max_minutes:g} min · {cost} · caller {mode}", "muted"),
    )
