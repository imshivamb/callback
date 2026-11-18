import asyncio
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from callback_voice.cli.console import console

if TYPE_CHECKING:
    from callback_voice.reference_agents.restaurant.server.serve_agent import LiveKitAccess


def register(app: typer.Typer) -> None:
    agent_app = typer.Typer(help="Run the bundled reference voice agents.", no_args_is_help=True)
    agent_app.command(
        "serve", help="Serve the restaurant agent over WebSocket (talk to it at http://HOST:PORT)."
    )(serve)
    agent_app.command(
        "phone-bridge",
        help="Put a WebSocket agent behind a phone number (for testing phone calls).",
    )(phone_bridge)
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
    livekit_url: str | None = typer.Option(
        None,
        "--livekit-url",
        help="Also answer new LiveKit rooms on this server (e.g. ws://127.0.0.1:7880). "
        "Joins with LIVEKIT_API_KEY and LIVEKIT_API_SECRET.",
    ),
    room_prefix: str = typer.Option(
        "callback", "--room-prefix", help="Answer LiveKit rooms named PREFIX-<call id>."
    ),
) -> None:
    from callback_voice.reference_agents.restaurant.server.configure_agent_logging import (
        configure_agent_logging,
    )
    from callback_voice.reference_agents.restaurant.server.serve_agent import serve_agent
    from callback_voice.reference_agents.restaurant.voice.behavior import BUGGY, GOOD

    behavior = BUGGY if buggy else GOOD
    livekit = _livekit_access(livekit_url, room_prefix) if livekit_url else None
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
        task = asyncio.create_task(serve_agent(behavior, host, port, ready, livekit=livekit))
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
        if livekit is not None:
            console.print(f"answering LiveKit rooms {room_prefix}-* on {livekit.url}")
        console.print(f"[muted]log  {log_path}[/]")
        await task

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("[muted]stopped[/]")


def phone_bridge(
    public_url: str = typer.Option(
        ...,
        "--public-url",
        help="Public https URL of a tunnel to --port (the provider connects through it).",
    ),
    provider: str = typer.Option("twilio", "--provider", help="Phone provider: twilio."),
    agent_url: str = typer.Option(
        "ws://127.0.0.1:8765", "--agent-url", help="The agent's WebSocket (raw PCM16, 16 kHz)."
    ),
    host: str = typer.Option("127.0.0.1", help="Interface to bind."),
    port: int = typer.Option(8767, help="Port the provider's media streams arrive on."),
    press_key_after: float | None = typer.Option(
        None,
        "--press-key-after",
        min=0.0,
        help="Seconds to wait, then press 1, before connecting the agent "
        "(for a Twilio trial account's message; try 8).",
    ),
) -> None:
    import os
    import secrets

    from callback_voice.errors import ConfigError
    from callback_voice.phone_bridge.serve_phone_bridge import (
        bridge_stream_url,
        serve_phone_bridge,
    )
    from callback_voice.telephony.providers import PROVIDERS

    if provider not in PROVIDERS:
        raise ConfigError(
            f"unknown --provider {provider!r}", hint=f"one of: {', '.join(sorted(PROVIDERS))}"
        )
    if not public_url.startswith("https://"):
        raise ConfigError(f"--public-url must start with https://, got {public_url!r}")
    if not agent_url.startswith(("ws://", "wss://")):
        raise ConfigError(f"--agent-url must start with ws:// or wss://, got {agent_url!r}")
    chosen = PROVIDERS[provider]
    token = os.environ.get("CALLBACK_PHONE_BRIDGE_TOKEN") or secrets.token_urlsafe(16)
    ready = asyncio.Event()

    async def main() -> None:
        task = asyncio.create_task(
            serve_phone_bridge(
                chosen.protocol(), agent_url, token, host, port, ready, press_key_after
            )
        )
        await asyncio.wait(
            {task, asyncio.create_task(ready.wait())}, return_when=asyncio.FIRST_COMPLETED
        )
        if task.done():
            task.result()
        console.print(
            f"Phone bridge ({provider}) · ws://{host}:{port} → {agent_url} · Ctrl+C to stop\n"
        )
        console.print(
            chosen.number_setup(bridge_stream_url(public_url, token)),
            markup=False,
            soft_wrap=True,  # copied into the provider's console: no inserted line breaks
        )
        console.print(
            "\n[muted]The URL holds a random token; set CALLBACK_PHONE_BRIDGE_TOKEN to keep "
            "it the same across restarts.[/]"
        )
        if press_key_after is not None:
            console.print(
                f"[warn]▲[/] presses 1 after {press_key_after:g} s on every call, "
                "then connects the agent."
            )
        await task

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("[muted]stopped[/]")
    except OSError as exc:
        raise ConfigError(f"cannot listen on port {port}: {exc}") from exc


def _livekit_access(url: str, room_prefix: str) -> "LiveKitAccess":
    from callback_voice.errors import ConfigError

    try:
        from callback_voice.reference_agents.restaurant.server.serve_agent import LiveKitAccess
        from callback_voice.transports.livekit_room import credentials
    except ImportError as exc:
        raise ConfigError(
            "--livekit-url needs the LiveKit SDK", hint='pip install "callback-voice[livekit]"'
        ) from exc
    if not url.startswith(("ws://", "wss://")):
        raise ConfigError(f"--livekit-url must start with ws:// or wss://, got {url!r}")
    key, secret = credentials("LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")
    return LiveKitAccess(url, key, secret, room_prefix)
