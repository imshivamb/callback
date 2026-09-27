"""Entry point: assembles the Typer app and maps errors to exit codes.

Exit codes are a contract with CI: 0 pass, 1 threshold or regression failure,
2 configuration or runtime error.
"""

import sys
from pathlib import Path

import typer

from callback_voice import __version__
from callback_voice.cli.commands import agent, baseline, doctor, replay, report, run, validate
from callback_voice.cli.console import console, err_console
from callback_voice.cli.render.error_panel import error_panel
from callback_voice.core.config.load_dotenv import load_dotenv
from callback_voice.errors import CallbackError

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERROR = 2

app = typer.Typer(
    name="callback",
    help="Chaos testing for voice agents. Real calls, real audio, one exit code.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)

for command in (run, replay, baseline, report, validate, doctor, agent):
    command.register(app)


def _version(value: bool) -> None:
    if value:
        console.print(f"callback {__version__}")
        raise typer.Exit(EXIT_PASS)


@app.callback()
def _root(
    version: bool = typer.Option(
        False, "--version", callback=_version, is_eager=True, help="Show the version and exit."
    ),
) -> None:
    """Chaos testing for voice agents."""


def main() -> None:
    """Console-script entry point."""
    load_dotenv(Path.cwd())
    try:
        # Outside standalone mode Click *returns* the code of `typer.Exit(n)` instead of
        # raising it, so it has to be passed on explicitly.
        code = app(standalone_mode=False)
        sys.exit(code if isinstance(code, int) else EXIT_PASS)
    except CallbackError as error:
        err_console.print(error_panel(error))
        sys.exit(EXIT_ERROR)
    except typer.Exit as done:
        sys.exit(done.exit_code)
    except typer.Abort:
        err_console.print("[muted]aborted[/]")
        sys.exit(EXIT_ERROR)
    except KeyboardInterrupt:
        err_console.print("[muted]interrupted[/]")
        sys.exit(EXIT_ERROR)
    except Exception as exc:
        # A usage error (missing argument, unknown command). Typer raises its own
        # vendored copy of Click's ClickException, and `click` itself is not a
        # dependency, so match on the interface rather than the class.
        show = getattr(exc, "show", None)
        if callable(show) and hasattr(exc, "exit_code"):
            show()
            sys.exit(EXIT_ERROR)
        # A bug is still a runtime error: exit 2, never 1 (which means "agent failed").
        err_console.print_exception(show_locals=False)
        sys.exit(EXIT_ERROR)
