import asyncio
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from importlib.resources import as_file, files
from importlib.util import find_spec
from pathlib import Path

import typer

from callback_voice.cli.console import console
from callback_voice.cli.render.run_summary import run_summary
from callback_voice.cli.render.trial_line import trial_line
from callback_voice.errors import ConfigError

_AGENT_START_TIMEOUT_S = 900.0  # the first run downloads the speech models


def register(app: typer.Typer) -> None:
    app.command(
        help="Call the bundled buggy agent with chaos, then open the report. No keys, no cost."
    )(demo)


def demo(
    good: bool = typer.Option(False, "--good", help="Call the good agent instead (it passes)."),
    open_report: bool = typer.Option(
        True, "--open/--no-open", help="Open the report in the browser when done."
    ),
) -> None:
    """Start a reference agent, run two chaos scenarios against it, open the report.

    Everything runs locally: scripted callers (no LLM), local speech models, and the
    reference agent in its own process. Exit code is the run's: 1 for the buggy agent.
    """
    from callback_voice.core.config.project_config import ProjectConfig
    from callback_voice.core.config.target_config import WebSocketTarget
    from callback_voice.core.models.scenario import Scenario
    from callback_voice.core.models.trial_result import TrialResult
    from callback_voice.core.runner.run_suite import run_suite
    from callback_voice.core.runner.runtime import Runtime
    from callback_voice.core.scenarios.load_suite import load_suite

    _check_local_speech()
    root = Path.cwd()
    logs = root / ".callback" / "demo-agent-logs"
    port = _free_port()
    label = "good" if good else "buggy"
    console.print(
        f"[bold]Callback demo[/] · calling the {label} reference agent with two chaos "
        "scenarios (barge-in, backchannel) · about 3 minutes\n"
    )
    agent = _start_agent(port, good, logs)
    try:
        project = ProjectConfig(
            targets={"demo-agent": WebSocketTarget(url=f"ws://127.0.0.1:{port}")}, root=root
        )
        with as_file(files("callback_voice.demo").joinpath("scenarios")) as folder:
            scenarios = load_suite(Path(folder))
        plan = [(s, t) for s in scenarios for t in range(1, s.trials + 1)]
        runtime = Runtime(project, "off", project.providers.llm)  # scripted: no LLM calls

        def on_trial(scenario: Scenario, trial: TrialResult) -> None:
            console.print(trial_line(trial, scenario.trials))

        result, run_dir = asyncio.run(run_suite(plan, runtime, on_trial=on_trial))
    finally:
        agent.terminate()
        try:
            agent.wait(timeout=10)
        except subprocess.TimeoutExpired:
            agent.kill()
    console.print(run_summary(result, run_dir))
    report = run_dir / "report.html"
    if open_report:
        webbrowser.open(report.resolve().as_uri())
        console.print("[muted]  opened the report; press N in it to hear each problem[/]")
    raise typer.Exit(result.exit_code)


def _check_local_speech() -> None:
    """Fail in one line, with the fix, before anything starts."""
    missing = [m for m in ("kokoro_onnx", "faster_whisper") if find_spec(m) is None]
    if missing:
        raise ConfigError(
            "the demo needs Callback's local speech models",
            hint='pip install "callback-voice[local]"',
        )
    from callback_voice.providers.tts.find_espeak import find_espeak

    if find_espeak() is None:
        raise ConfigError(
            "the demo's local voice needs espeak-ng, which is not installed",
            hint="macOS: brew install espeak-ng  ·  Debian/Ubuntu: sudo apt install espeak-ng",
        )


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _start_agent(port: int, good: bool, logs: Path) -> subprocess.Popen[bytes]:
    """Run ``callback agent serve`` in its own process and wait until it answers."""
    logs.mkdir(parents=True, exist_ok=True)
    stderr = (logs / f"{time.strftime('%Y%m%d-%H%M%S')}-{port}.stderr").open("wb")
    flags = [] if good else ["--buggy"]
    command = [sys.executable, "-m", "callback_voice.cli", "agent", "serve", "--port", str(port)]
    process = subprocess.Popen(
        [*command, "--log-dir", str(logs), *flags],
        stdout=subprocess.DEVNULL,
        stderr=stderr,
        env=os.environ.copy(),
    )
    deadline = time.monotonic() + _AGENT_START_TIMEOUT_S
    with console.status(
        "[muted]starting the agent (the first run downloads speech models, ~500 MB)…[/]"
    ):
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise ConfigError(
                    "the demo agent stopped while starting", hint=f"see {stderr.name}"
                )
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
                return process
            except OSError:
                time.sleep(0.5)
    process.kill()
    raise ConfigError("the demo agent did not start in time", hint=f"see {stderr.name}")
