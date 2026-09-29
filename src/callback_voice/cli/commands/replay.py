import asyncio
from pathlib import Path

import typer

from callback_voice.cli.console import console
from callback_voice.cli.render.run_summary import run_summary
from callback_voice.cli.render.trial_line import trial_line
from callback_voice.core.config.load_project_config import load_project_config
from callback_voice.core.models.scenario import Scenario
from callback_voice.core.models.trial_result import TrialResult
from callback_voice.core.runner.compare_calls import compare_calls
from callback_voice.core.runner.find_call import find_call
from callback_voice.core.scenarios.load_scenario import load_scenario
from callback_voice.errors import ConfigError


def register(app: typer.Typer) -> None:
    app.command(help="Re-run one call with the same seed, caller and chaos, and check it matches.")(
        replay
    )


def replay(
    call_id: str = typer.Argument(
        ..., help="The call id, e.g. move-booking--t1 (see results.json)."
    ),
    run_id: str | None = typer.Option(
        None, "--run", help="Run to take the call from (default: latest)."
    ),
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to callback.yaml."),
) -> None:
    from callback_voice.core.runner.ci_limits import apply_ci_limits
    from callback_voice.core.runner.run_suite import run_suite
    from callback_voice.core.runner.runtime import Runtime

    project = load_project_config(config)
    found = find_call(project.resolve(project.output_dir), call_id, run_id)
    if found.scenario.source is None or not Path(found.scenario.source).is_file():
        raise ConfigError(f"the scenario file for {call_id} is gone: {found.scenario.source}")
    [scenario], overrides = apply_ci_limits(
        [
            load_scenario(Path(found.scenario.source)).model_copy(
                update={"agent": found.scenario.agent}
            )
        ]
    )
    trial = found.trial
    console.print(
        f"[muted]REPLAY[/]  [bold]{call_id}[/] [muted]from run {found.run.run_id} · seed {trial.seed} "
        f"· agent {scenario.agent}[/]\n"
    )

    def on_trial(s: Scenario, result: TrialResult) -> None:
        console.print(trial_line(result, s.trials))

    runtime = Runtime(
        project,
        "replay" if scenario.caller.script is None else project.recorded,
        project.providers.llm,
    )
    result, run_dir = asyncio.run(
        run_suite(
            [(scenario, trial.trial)],
            runtime,
            on_trial=on_trial,
            seeds={(scenario.id, trial.trial): trial.seed},
            limit_overrides=overrides,
        )
    )
    console.print(run_summary(result, run_dir))

    replayed = result.scenarios[0].trials[0]
    if trial.call is None or replayed.call is None:
        raise typer.Exit(result.exit_code)
    same = compare_calls(trial.call.events, replayed.call.events)
    console.print(
        f"\n  caller lines  {'[pass]identical[/]' if same.lines_match else '[fail]differ[/]'}"
        f"  ({len(same.replayed_lines)})"
    )
    console.print(
        f"  chaos         {'[pass]identical[/]' if same.chaos_match else '[fail]differ[/]'}"
        f"  ({len(same.replayed_chaos)} action(s))"
    )
    raise typer.Exit(result.exit_code if same.exact else 1)
