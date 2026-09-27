from pathlib import Path

import typer

from callback_voice.cli.console import console
from callback_voice.core.config.load_project_config import load_project_config


def register(app: typer.Typer) -> None:
    baseline_app = typer.Typer(
        help="Save runs as baselines that later runs are compared with.", no_args_is_help=True
    )
    baseline_app.command("save", help="Save a run (the latest by default) as baseline NAME.")(save)
    app.add_typer(baseline_app, name="baseline")


def save(
    name: str = typer.Argument(..., help="Baseline name, e.g. main."),
    run: str | None = typer.Option(None, "--run", help="Run id to save instead of the latest."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to callback.yaml."),
) -> None:
    from callback_voice.core.baseline.save_baseline import baseline_path, save_baseline

    project = load_project_config(config, start=Path.cwd())
    baseline_dir = project.resolve(project.baseline_dir)
    saved = save_baseline(project.resolve(project.output_dir), baseline_dir, name, run)
    count = sum(len(a) for a in saved.scenarios.values())
    console.print(
        f"[pass]saved[/] baseline [bold]{name}[/] from run {saved.run_id} "
        f"[muted]({len(saved.scenarios)} scenario(s), {count} aggregate(s))[/]\n"
        f"[muted]  {baseline_path(baseline_dir, name)}[/]\n"
        f"[muted]  compare with[/] callback run <path> --baseline {name}"
    )
