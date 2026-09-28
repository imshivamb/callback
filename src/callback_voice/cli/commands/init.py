from importlib.resources import files
from pathlib import Path

import typer

from callback_voice.cli.console import console
from callback_voice.errors import ConfigError

_FILES = {"callback.yaml": "callback.yaml", "scenarios/example.yaml": "example.yaml"}


def register(app: typer.Typer) -> None:
    app.command(help="Create callback.yaml and an example scenario in this folder.")(init)


def init(
    force: bool = typer.Option(False, "--force", help="Overwrite files that already exist."),
) -> None:
    root = Path.cwd()
    existing = [name for name in _FILES if (root / name).exists()]
    if existing and not force:
        raise ConfigError(
            f"already exists: {', '.join(existing)}", hint="pass --force to overwrite"
        )
    templates = files("callback_voice.init_templates")
    for name, template in _FILES.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(templates.joinpath(template).read_text("utf-8"), encoding="utf-8")
        console.print(f"[pass]created[/] {name}")
    console.print(
        "\n[bold]Next[/]\n"
        "  callback doctor                 check speech models and keys\n"
        "  callback agent serve            start the example agent (another terminal)\n"
        "  callback run scenarios          call it; exit 0 pass, 1 fail, 2 error\n"
        "\n[muted]Add .callback/ to your .gitignore: runs and recordings go there.[/]"
    )
