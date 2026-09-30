from rich.text import Text

from callback_voice.core.models.scenario import Scenario


def rules_notice(scenarios: list[Scenario], judge_configured: bool) -> Text | None:
    """Before any call: which plain-English ``must_not`` rules will go unchecked.

    They need the LLM judge; without one they are recorded as not checked, never as
    passed.
    """
    if judge_configured:
        return None
    counts = {
        s.id: n for s in scenarios if (n := sum(isinstance(r, str) for r in s.expect.must_not))
    }
    if not counts:
        return None
    total = sum(counts.values())
    names = ", ".join(counts)
    return Text(
        f"▲ {total} plain-English must_not rule(s) in {names} won't be checked: they need "
        "the LLM judge (providers.judge in callback.yaml). Pattern rules are checked.\n",
        style="warn",
    )
