import asyncio
import logging

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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log the conversation."),
) -> None:
    from callback_voice.reference_agents.restaurant.server.serve_agent import serve_agent
    from callback_voice.reference_agents.restaurant.voice.behavior import BUGGY, GOOD

    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("httpx", "httpcore", "faster_whisper", "websockets"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    behavior = BUGGY if buggy else GOOD
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
        console.print(
            f"Olive & Ember ({label}) · ws://{host}:{port} · talk in a browser at "
            f"[brand]http://{host}:{port}[/] · Ctrl+C to stop"
        )
        await task

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("[muted]stopped[/]")
