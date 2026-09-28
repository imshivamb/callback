import asyncio
from dataclasses import replace
from pathlib import Path

import typer

from callback_voice.cli.console import console


def register(app: typer.Typer) -> None:
    agent_app = typer.Typer(help="Run the bundled reference voice agents.", no_args_is_help=True)
    agent_app.command(
        "serve", help="Serve the restaurant agent over WebSocket (talk to it at http://HOST:PORT)."
    )(serve)
    app.add_typer(agent_app, name="agent")


def serve(
    buggy: bool = typer.Option(False, "--buggy", help="Run the deliberately buggy copy."),
    host: str = typer.Option("127.0.0.1", help="Interface to bind."),
    port: int = typer.Option(8765, help="Port for WebSocket audio and HTTP."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Also print the conversation log."),
    log_dir: Path = typer.Option(
        Path(".callback/agent-logs"), "--log-dir", help="Where each run's log file is written."
    ),
    add_latency: float = typer.Option(
        0.0,
        "--add-latency",
        min=0.0,
        help="Wait this many extra seconds before every reply (simulate a slower agent).",
    ),
    synthesis_delay: float = typer.Option(
        0.0,
        "--synthesis-delay",
        min=0.0,
        help="Wait this long before synthesising each sentence (simulate a slow machine).",
    ),
) -> None:
    from callback_voice.reference_agents.restaurant.server.configure_agent_logging import (
        configure_agent_logging,
    )
    from callback_voice.reference_agents.restaurant.server.serve_agent import serve_agent
    from callback_voice.reference_agents.restaurant.voice.behavior import BUGGY, GOOD

    behavior = BUGGY if buggy else GOOD
    if add_latency:
        behavior = replace(
            behavior,
            name=f"{behavior.name}+{add_latency:g}s",
            think_delay_s=behavior.think_delay_s + add_latency,
        )
    if synthesis_delay:
        behavior = replace(
            behavior,
            name=f"{behavior.name}+slow-tts",
            synthesis_delay_s=synthesis_delay,
        )
    log_path = configure_agent_logging(log_dir, behavior.name, port, verbose=verbose)
    ready = asyncio.Event()

    async def main() -> None:
        task = asyncio.create_task(serve_agent(behavior, host, port, ready))
        with console.status("[muted]loading speech models…[/]", spinner="dots"):
            done, _ = await asyncio.wait(
                {task, asyncio.create_task(ready.wait())}, return_when=asyncio.FIRST_COMPLETED
            )
            if task in done:
                task.result()
        label = "[fail]buggy[/]" if buggy else "[pass]good[/]"
        if add_latency:
            label += f" [warn]+{add_latency:g} s latency[/]"
        console.print(
            f"Olive & Ember ({label}) · ws://{host}:{port} · talk in a browser at "
            f"[brand]http://{host}:{port}[/] · Ctrl+C to stop"
        )
        console.print(f"[muted]log  {log_path}[/]")
        await task

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("[muted]stopped[/]")
