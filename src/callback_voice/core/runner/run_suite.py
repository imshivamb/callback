import asyncio
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from callback_voice import __version__
from callback_voice.core.baseline.compare_to_baseline import compare_to_baseline
from callback_voice.core.models.baseline import Baseline
from callback_voice.core.models.limit_override import LimitOverride
from callback_voice.core.models.run_result import RunResult
from callback_voice.core.models.scenario import Scenario
from callback_voice.core.models.scenario_result import ScenarioResult
from callback_voice.core.models.trial_result import TrialResult
from callback_voice.core.runner.exit_code import EXIT_PASS, exit_code
from callback_voice.core.runner.run_metadata import agent_config_hash, git_sha, new_run_id
from callback_voice.core.runner.run_trial import run_trial
from callback_voice.core.runner.runtime import Runtime
from callback_voice.core.runner.scenario_verdict import scenario_verdict
from callback_voice.core.seeds.derive_seed import derive_seed
from callback_voice.report.write_junit import write_junit
from callback_voice.report.write_report import write_report
from callback_voice.scoring.aggregate.aggregate_scenario import aggregate_scenario

type OnTrial = Callable[[Scenario, TrialResult], None]


async def run_suite(
    plan: list[tuple[Scenario, int]],
    runtime: Runtime,
    *,
    base_seed: int = 0,
    on_trial: OnTrial | None = None,
    seeds: dict[tuple[str, int], int] | None = None,
    baseline: Baseline | None = None,
    min_effect: Mapping[str, float] | None = None,
    limit_overrides: list[LimitOverride] | None = None,
) -> tuple[RunResult, Path]:
    """Run every (scenario, trial), aggregate, compare, and write the result files.

    Up to ``concurrency`` calls (callback.yaml, default 1) run at once. Trial seeds
    depend only on the base seed, scenario id and trial number, so the same trial
    always replays the same caller whatever the order calls finish in. Writes
    ``results.json``, ``junit.xml`` and ``report.html`` into the run folder.
    """
    project = runtime.project
    run_id = new_run_id()
    run_dir = project.resolve(project.output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    await runtime.warm_up(list({s.id: s for s, _ in plan}.values()))

    scenarios = {s.id: s for s, _ in plan}
    slots = asyncio.Semaphore(project.concurrency)

    async def one(scenario: Scenario, trial: int) -> TrialResult:
        seed = (seeds or {}).get((scenario.id, trial), derive_seed(base_seed, scenario.id, trial))
        async with slots:
            trial_result = await run_trial(scenario, trial, seed, runtime, run_dir)
        if on_trial is not None:
            on_trial(scenario, trial_result)
        return trial_result

    finished = await asyncio.gather(*(one(s, t) for s, t in plan))
    by_scenario: dict[str, list[TrialResult]] = {}
    for trial_result in finished:  # plan order, not finishing order
        by_scenario.setdefault(trial_result.scenario_id, []).append(trial_result)

    scenario_results = [
        _scenario_result(scenarios[sid], trials, derive_seed(base_seed, sid, "aggregate"))
        for sid, trials in by_scenario.items()
    ]
    diffs = (
        compare_to_baseline(scenario_results, baseline, min_effect or {})
        if baseline is not None
        else []
    )
    code = exit_code(scenario_results, diffs)
    result = RunResult(
        run_id=run_id,
        created_at=datetime.now(UTC),
        callback_version=__version__,
        git_sha=git_sha(project.root),
        agent_config_hash=agent_config_hash(project),
        mode=runtime.recorded,
        concurrency=project.concurrency,
        providers={k: v.name for k, v in project.providers if v is not None}
        | {"llm": runtime.llm_choice.name},
        provider_models={
            k: v.model or v.voice
            for k, v in project.providers
            if v is not None and k != "llm" and (v.model or v.voice)
        }
        | {"llm": runtime.llm.model},
        vad={"provider": project.providers.vad.name},
        judge=runtime.judge_info,
        scenarios=scenario_results,
        limit_overrides=limit_overrides or [],
        baseline_name=baseline.name if baseline is not None else None,
        baseline_diff=diffs,
        passed=code == EXIT_PASS,
        exit_code=code,
        duration_s=round(time.monotonic() - started, 2),
    )
    (run_dir / "results.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    write_junit(result, run_dir / "junit.xml")
    write_report(result, run_dir)
    return result, run_dir


def _scenario_result(scenario: Scenario, trials: list[TrialResult], seed: int) -> ScenarioResult:
    aggregates = aggregate_scenario(trials, scenario.expect.thresholds, seed)
    passed, reasons = scenario_verdict(trials, aggregates)
    return ScenarioResult(
        scenario_id=scenario.id,
        agent=scenario.agent,
        source=str(scenario.source) if scenario.source else None,
        passed=passed,
        trials=trials,
        aggregates=aggregates,
        failure_reasons=reasons,
    )
