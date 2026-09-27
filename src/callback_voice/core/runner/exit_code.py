from callback_voice.core.models.scenario_result import ScenarioResult

EXIT_PASS, EXIT_FAIL, EXIT_ERROR = 0, 1, 2


def exit_code(scenarios: list[ScenarioResult]) -> int:
    """0 all passed, 1 something failed, 2 something could not run. Errors win."""
    trials = [t for s in scenarios for t in s.trials]
    if any(t.error for t in trials):
        return EXIT_ERROR
    return EXIT_PASS if all(s.passed for s in scenarios) else EXIT_FAIL
