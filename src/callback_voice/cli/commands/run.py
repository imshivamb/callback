import asyncio
from pathlib import Path

import typer

from callback_voice.cli.console import console
from callback_voice.cli.render.run_plan import run_plan
from callback_voice.cli.render.run_summary import run_summary
from callback_voice.cli.render.trial_line import trial_line
from callback_voice.core.config.load_project_config import load_project_config
from callback_voice.core.config.project_config import RecordedMode
from callback_voice.core.config.provider_config import LOCAL_CALLER_LLM
from callback_voice.core.models.scenario import Scenario
from callback_voice.core.models.trial_result import TrialResult
from callback_voice.core.runner.estimate_cost import estimate_cost
from callback_voice.core.scenarios.check_targets_exist import check_targets_exist
from callback_voice.core.scenarios.load_suite import load_suite
from callback_voice.errors import ConfigError


def register(app: typer.Typer) -> None:
    app.command(help="Run scenarios against their agents. Exit 0 pass, 1 fail, 2 error.")(run)


def run(
    path: Path = typer.Argument(..., help="A scenario file or a directory of them."),
    trials: int | None = typer.Option(
        None, "--trials", "-n", min=1, help="Override trials per scenario."
    ),
    seed: int = typer.Option(0, "--seed", help="Base seed; the same seed replays the same calls."),
    record: bool = typer.Option(
        False, "--record", help="Always call the LLM and re-record callers."
    ),
    replay: bool = typer.Option(
        False, "--replay", help="Only replay recorded callers (zero LLM calls)."
    ),
    local: bool = typer.Option(False, "--local", help="Use a local Ollama model for the caller."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Don't ask before exceeding the cost cap."),
    agent: str | None = typer.Option(
        None, "--agent", "-a", help="Run every scenario against this target instead."
    ),
    baseline: str | None = typer.Option(
        None, "--baseline", "-b", help="Compare with this saved baseline; a regression exits 1."
    ),
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to callback.yaml."),
) -> None:
    from callback_voice.core.baseline.load_baseline import load_baseline
    from callback_voice.core.baseline.min_effect import min_effect
    from callback_voice.core.runner.run_suite import run_suite
    from callback_voice.core.runner.runtime import Runtime

    if record and replay:
        raise ConfigError("--record and --replay cannot be used together")
    project = load_project_config(config, start=path if path.is_dir() else path.parent)
    scenarios = load_suite(path)
    if agent is not None:
        scenarios = [s.model_copy(update={"agent": agent}) for s in scenarios]
    check_targets_exist(scenarios, project)
    # Before any call is placed: a missing baseline or a bad min_effect is exit 2 now.
    reference = load_baseline(project.resolve(project.baseline_dir), baseline) if baseline else None
    effects = min_effect(project.min_effect)
    mode: RecordedMode = "record" if record else "replay" if replay else project.recorded
    llm_choice = LOCAL_CALLER_LLM if local else project.providers.llm
    plan = [(s, t) for s in scenarios for t in range(1, (trials or s.trials) + 1)]

    runtime = Runtime(project, mode, llm_choice)
    judge = runtime.judge
    estimate = estimate_cost(
        plan,
        runtime.llm.usd_per_1k_tokens if _uses_llm(plan) and mode != "replay" else 0.0,
        replaying=mode == "replay",
        judge_usd_per_1k=judge.usd_per_1k_tokens if judge is not None else None,
    )
    judge_name = project.providers.judge.name if project.providers.judge else None
    console.print(run_plan(estimate, llm_choice.name, judge_name, mode))
    if estimate.usd > project.cost_cap_usd and not yes:
        if not console.is_terminal:
            raise ConfigError(
                f"estimated cost ${estimate.usd:.2f} exceeds cost_cap_usd ${project.cost_cap_usd:.2f}",
                hint="pass --yes, or raise cost_cap_usd in callback.yaml",
            )
        typer.confirm(
            f"Estimated ${estimate.usd:.2f} exceeds your ${project.cost_cap_usd:.2f} cap. Continue?",
            abort=True,
        )
    console.print()

    def on_trial(scenario: Scenario, result: TrialResult) -> None:
        console.print(trial_line(result, trials or scenario.trials))

    result, run_dir = asyncio.run(
        run_suite(
            plan,
            runtime,
            base_seed=seed,
            on_trial=on_trial,
            baseline=reference,
            min_effect=effects,
        )
    )
    console.print(run_summary(result, run_dir))
    raise typer.Exit(result.exit_code)


def _uses_llm(plan: list[tuple[Scenario, int]]) -> bool:
    return any(s.caller.script is None for s, _ in plan)
