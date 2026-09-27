from pathlib import Path

from rich.console import Group
from rich.text import Text

from callback_voice.cli.render.aggregate_lines import aggregate_lines
from callback_voice.core.models.run_result import RunResult

_VERDICT = {0: ("PASS", "pass"), 1: ("FAIL", "fail"), 2: ("ERROR", "fail")}


def run_summary(result: RunResult, run_dir: Path) -> Group:
    trials = [t for s in result.scenarios for t in s.trials]
    word, style = _VERDICT[result.exit_code]
    passed = sum(t.passed for t in trials)
    scenarios = [
        aggregate_lines(s, [d for d in result.baseline_diff if d.scenario_id == s.scenario_id])
        for s in result.scenarios
    ]
    regressions = [d for d in result.baseline_diff if d.regressed]
    compared = (
        f" · vs baseline {result.baseline_name}: {len(regressions)} regression(s)"
        if result.baseline_name
        else ""
    )
    return Group(
        Text(),
        *scenarios,
        Text.assemble(
            "\n",
            (f" {word} ", f"{style} reverse"),
            (
                f"  {sum(s.passed for s in result.scenarios)}/{len(result.scenarios)} scenario(s) "
                f"passed · {passed}/{len(trials)} call(s) passed{compared} · "
                f"{result.duration_s:.0f} s · exit {result.exit_code}\n",
                "bold",
            ),
            ("  results  ", "muted"),
            (str(run_dir / "results.json"), "brand"),
            ("\n  junit    ", "muted"),
            (str(run_dir / "junit.xml"), "brand"),
        ),
    )
