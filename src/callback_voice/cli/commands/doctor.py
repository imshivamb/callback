from pathlib import Path

import typer

from callback_voice.cli.console import console
from callback_voice.cli.render.check_table import check_table
from callback_voice.core.config.load_project_config import load_project_config


def register(app: typer.Typer) -> None:
    app.command(help="Check audio deps, models, keys and targets. Never needs a key.")(doctor)


def doctor(
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to callback.yaml."),
) -> None:
    from callback_voice.doctor.run_checks import run_checks

    project = load_project_config(config)
    with console.status("[muted]checking environment…[/]", spinner="dots"):
        results = run_checks(project)
    console.print()
    console.print(check_table(results))

    failed = sum(r.status == "fail" for r in results)
    warned = sum(r.status == "warn" for r in results)
    if failed:
        console.print(f"[fail]{failed} blocking problem(s).[/] Fix them before running calls.")
        raise typer.Exit(2)
    summary = (
        "[pass]Ready.[/]"
        if not warned
        else f"[pass]Core ready.[/] [warn]{warned} optional item(s) need attention.[/]"
    )
    console.print(summary)
