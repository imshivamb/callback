from pathlib import Path

from callback_voice.core.models.scenario import Scenario
from callback_voice.core.scenarios.discover_scenario_files import discover_scenario_files
from callback_voice.core.scenarios.load_scenario import load_scenario
from callback_voice.errors import ScenarioError


def load_suite(path: Path) -> list[Scenario]:
    """Load every scenario under ``path``; reports all invalid files at once, not just the first."""
    scenarios: list[Scenario] = []
    problems: list[str] = []
    for file in discover_scenario_files(path):
        try:
            scenarios.append(load_scenario(file))
        except ScenarioError as exc:
            problems.append(str(exc))
    if problems:
        raise ScenarioError("\n".join(problems))

    seen: dict[str, Path | None] = {}
    for scenario in scenarios:
        if scenario.id in seen:
            raise ScenarioError(
                f"duplicate scenario id {scenario.id!r} in {seen[scenario.id]} and {scenario.source}"
            )
        seen[scenario.id] = scenario.source
    return scenarios
