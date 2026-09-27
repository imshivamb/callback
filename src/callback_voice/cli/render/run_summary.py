from pathlib import Path

from rich.text import Text

from callback_voice.core.models.run_result import RunResult

_VERDICT = {0: ("PASS", "pass"), 1: ("FAIL", "fail"), 2: ("ERROR", "fail")}


def run_summary(result: RunResult, run_dir: Path) -> Text:
    trials = [t for s in result.scenarios for t in s.trials]
    word, style = _VERDICT[result.exit_code]
    passed = sum(t.passed for t in trials)
    return Text.assemble(
        "\n",
        (f" {word} ", f"{style} reverse"),
        (
            f"  {passed}/{len(trials)} call(s) passed · {result.duration_s:.0f} s · exit {result.exit_code}\n",
            "bold",
        ),
        ("  results  ", "muted"),
        (str(run_dir / "results.json"), "brand"),
    )
