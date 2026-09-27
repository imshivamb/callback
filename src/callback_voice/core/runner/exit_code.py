from collections.abc import Sequence

from callback_voice.core.models.baseline_diff import BaselineDiff
from callback_voice.core.models.scenario_result import ScenarioResult

EXIT_PASS, EXIT_FAIL, EXIT_ERROR = 0, 1, 2


def exit_code(scenarios: list[ScenarioResult], baseline_diff: Sequence[BaselineDiff] = ()) -> int:
    """0 all passed, 1 something failed or regressed, 2 something could not run. Errors win."""
    trials = [t for s in scenarios for t in s.trials]
    if any(t.error for t in trials):
        return EXIT_ERROR
    if any(d.regressed for d in baseline_diff):
        return EXIT_FAIL
    return EXIT_PASS if all(s.passed for s in scenarios) else EXIT_FAIL
