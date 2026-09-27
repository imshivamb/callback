import webbrowser
from pathlib import Path

import typer

from callback_voice.cli.console import console
from callback_voice.errors import ConfigError


def register(app: typer.Typer) -> None:
    app.command(help="Rebuild a run's single-file HTML report from its results and recordings.")(
        report
    )


def report(
    run_dir: Path = typer.Argument(..., help="A run folder, e.g. .callback/runs/20260927-130139."),
    audio: bool = typer.Option(
        True, "--audio/--no-audio", help="Embed each call's audio (about 270 KB a minute)."
    ),
    open_it: bool = typer.Option(False, "--open", help="Open the report in the browser."),
) -> None:
    from callback_voice.core.models.run_result import RunResult
    from callback_voice.report.write_report import write_report

    results = run_dir / "results.json"
    if not results.is_file():
        raise ConfigError(
            f"no results.json in {run_dir}", hint="pass a folder under .callback/runs"
        )
    result = RunResult.model_validate_json(results.read_text(encoding="utf-8"))
    path = write_report(result, run_dir, audio=audio)
    size = path.stat().st_size / 1_000_000
    console.print(f"[pass]report[/] [brand]{path}[/] [muted]({size:.1f} MB)[/]")
    if open_it:
        webbrowser.open(path.resolve().as_uri())
