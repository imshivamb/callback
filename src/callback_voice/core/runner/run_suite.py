import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from callback_voice import __version__
from callback_voice.core.models.run_result import RunResult
from callback_voice.core.models.scenario import Scenario
from callback_voice.core.models.scenario_result import ScenarioResult
from callback_voice.core.models.trial_result import TrialResult
from callback_voice.core.runner.exit_code import EXIT_PASS, exit_code
from callback_voice.core.runner.run_metadata import agent_config_hash, git_sha, new_run_id
from callback_voice.core.runner.run_trial import run_trial
from callback_voice.core.runner.runtime import Runtime
from callback_voice.core.seeds.derive_seed import derive_seed

type OnTrial = Callable[[Scenario, TrialResult], None]


async def run_suite(
    plan: list[tuple[Scenario, int]],
    runtime: Runtime,
    *,
    base_seed: int = 0,
    on_trial: OnTrial | None = None,
    seeds: dict[tuple[str, int], int] | None = None,
) -> tuple[RunResult, Path]:
    """Run every (scenario, trial) in order and write ``results.json``.

    Trial seeds depend only on the base seed, scenario id and trial number, so the
    same trial always replays the same caller.
    """
    project = runtime.project
    run_id = new_run_id()
    run_dir = project.resolve(project.output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    await runtime.warm_up(list({s.id: s for s, _ in plan}.values()))

    by_scenario: dict[str, list[TrialResult]] = {}
    scenarios = {s.id: s for s, _ in plan}
    for scenario, trial in plan:
        seed = (seeds or {}).get((scenario.id, trial), derive_seed(base_seed, scenario.id, trial))
        trial_result = await run_trial(scenario, trial, seed, runtime, run_dir)
        by_scenario.setdefault(scenario.id, []).append(trial_result)
        if on_trial is not None:
            on_trial(scenario, trial_result)

    scenario_results = [
        ScenarioResult(
            scenario_id=sid,
            agent=scenarios[sid].agent,
            source=str(scenarios[sid].source) if scenarios[sid].source else None,
            passed=all(t.passed for t in trials),
            trials=trials,
            failure_reasons=sorted({r for t in trials for r in t.failure_reasons}),
        )
        for sid, trials in by_scenario.items()
    ]
    code = exit_code(scenario_results)
    result = RunResult(
        run_id=run_id,
        created_at=datetime.now(UTC),
        callback_version=__version__,
        git_sha=git_sha(project.root),
        agent_config_hash=agent_config_hash(project),
        mode=runtime.recorded,
        providers={k: v.name for k, v in project.providers if v is not None}
        | {"llm": runtime.llm_choice.name},
        vad={"provider": project.providers.vad.name},
        scenarios=scenario_results,
        passed=code == EXIT_PASS,
        exit_code=code,
        duration_s=round(time.monotonic() - started, 2),
    )
    (run_dir / "results.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result, run_dir
