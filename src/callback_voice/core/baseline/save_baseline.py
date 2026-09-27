import re
from datetime import UTC, datetime
from pathlib import Path

from callback_voice.core.models.baseline import Baseline
from callback_voice.core.models.run_result import RunResult
from callback_voice.errors import ConfigError

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def baseline_path(baseline_dir: Path, name: str) -> Path:
    if not _NAME.fullmatch(name):
        raise ConfigError(
            f"invalid baseline name {name!r}", hint="use letters, digits, '.', '_' and '-'"
        )
    return baseline_dir / f"{name}.json"


def save_baseline(runs_dir: Path, baseline_dir: Path, name: str, run_id: str | None) -> Baseline:
    """Store a run's scenario aggregates (the latest run by default) as ``NAME.json``.

    A run that errored is refused: it has no trustworthy numbers to compare against.
    """
    path = baseline_path(baseline_dir, name)
    run = _find_run(runs_dir, run_id)
    if run.exit_code == 2:
        raise ConfigError(
            f"run {run.run_id} errored (exit 2); it cannot be a baseline",
            hint="fix the error and run again, or pass --run with another run id",
        )
    baseline = Baseline(
        name=name,
        saved_at=datetime.now(UTC),
        run_id=run.run_id,
        git_sha=run.git_sha,
        agent_config_hash=run.agent_config_hash,
        scenarios={s.scenario_id: s.aggregates for s in run.scenarios},
    )
    baseline_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(baseline.model_dump_json(indent=2), encoding="utf-8")
    return baseline


def _find_run(runs_dir: Path, run_id: str | None) -> RunResult:
    if run_id is not None:
        results = runs_dir / run_id / "results.json"
        if not results.is_file():
            raise ConfigError(f"no run {run_id!r} in {runs_dir}")
    else:
        found = sorted(runs_dir.glob("*/results.json"), reverse=True)
        if not found:
            raise ConfigError(f"no runs in {runs_dir}", hint="run `callback run` first")
        results = found[0]
    run = RunResult.model_validate_json(results.read_text(encoding="utf-8"))
    if run.scenarios and not any(s.aggregates for s in run.scenarios):
        raise ConfigError(
            f"run {run.run_id} has no aggregates (made by an older Callback)",
            hint="run the suite again, then save that run",
        )
    return run
