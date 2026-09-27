from pathlib import Path

import typer

from callback_voice.cli.console import console
from callback_voice.core.config.load_project_config import load_project_config
from callback_voice.core.scenarios.check_targets_exist import check_targets_exist
from callback_voice.core.scenarios.load_suite import load_suite


def register(app: typer.Typer) -> None:
    app.command(help="Validate scenario files. Exits 2 with the exact problem.")(validate)


def validate(
    path: Path = typer.Argument(..., help="A scenario file or a directory of them."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to callback.yaml."),
) -> None:
    project = load_project_config(config, start=path if path.is_dir() else path.parent)
    scenarios = load_suite(path)
    check_targets_exist(scenarios, project)
    for scenario in scenarios:
        events = len(scenario.chaos.events) + (1 if scenario.chaos.noise else 0)
        console.print(
            f"[pass]✓[/] {scenario.id}  [muted]{scenario.trials} trial(s) · {events} chaos event(s) · "
            f"agent {scenario.agent}[/]"
        )
    console.print(f"\n[pass]{len(scenarios)} scenario(s) valid.[/]")
