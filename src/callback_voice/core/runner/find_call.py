from dataclasses import dataclass
from pathlib import Path

from callback_voice.core.models.run_result import RunResult
from callback_voice.core.models.scenario_result import ScenarioResult
from callback_voice.core.models.trial_result import TrialResult
from callback_voice.errors import ConfigError


@dataclass(frozen=True, slots=True)
class FoundCall:
    run: RunResult
    scenario: ScenarioResult
    trial: TrialResult


def find_call(runs_dir: Path, call_id: str, run_id: str | None = None) -> FoundCall:
    """The most recent run (or ``run_id``) containing ``call_id``."""
    candidates = [runs_dir / run_id] if run_id else sorted(runs_dir.glob("*"), reverse=True)
    for run_dir in candidates:
        results = run_dir / "results.json"
        if not results.is_file():
            continue
        run = RunResult.model_validate_json(results.read_text(encoding="utf-8"))
        for scenario in run.scenarios:
            for trial in scenario.trials:
                if trial.call_id == call_id:
                    return FoundCall(run, scenario, trial)
    raise ConfigError(
        f"no call {call_id!r} in {runs_dir}", hint="call ids are listed in each results.json"
    )
