"""Calls through a self-hosted LiveKit server: the reference agent answers the room
Callback creates, and the call is scored like any other.

Needs the `livekit-server` binary (e.g. `brew install livekit`) and
`pip install "callback-voice[livekit,local]"`; skips without them.
"""

import asyncio
import json
import secrets
import shutil
import socket
import subprocess
import time
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path

import pytest

from callback_voice.core.config.target_config import LiveKitTarget, WebSocketTarget
from callback_voice.errors import ConfigError
from callback_voice.scoring.verifiers.resolve_webhook import resolve_webhook
from tests.e2e.conftest import AGENT_LOGS, RunningAgent, _serve

HAS_LIVEKIT = find_spec("livekit") is not None
needs_sdk = pytest.mark.skipif(
    not HAS_LIVEKIT, reason='needs pip install "callback-voice[livekit]"'
)
needs_server = pytest.mark.skipif(
    not HAS_LIVEKIT
    or shutil.which("livekit-server") is None
    or find_spec("kokoro_onnx") is None
    or find_spec("faster_whisper") is None,
    reason='needs livekit-server and pip install "callback-voice[livekit,local]"',
)
PREFIX = "cbtest"


def _free_port(kind: int = socket.SOCK_STREAM) -> int:
    with socket.socket(socket.AF_INET, kind) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@dataclass
class LiveKitServer:
    url: str
    key: str
    secret: str

    @property
    def env(self) -> dict[str, str]:
        return {"LIVEKIT_API_KEY": self.key, "LIVEKIT_API_SECRET": self.secret}


@pytest.fixture(scope="module")
def livekit_server() -> Iterator[LiveKitServer]:
    """A private livekit-server on free ports, with a random key for this test run."""
    port, tcp, udp = _free_port(), _free_port(), _free_port(socket.SOCK_DGRAM)
    key, secret = "callback-test", secrets.token_hex(32)
    config = (
        f"port: {port}\n"
        "bind_addresses: ['127.0.0.1']\n"
        f"rtc: {{tcp_port: {tcp}, udp_port: {udp}, use_external_ip: false}}\n"
        f"keys: {{{key}: {secret}}}\n"
    )
    AGENT_LOGS.mkdir(parents=True, exist_ok=True)
    log = (AGENT_LOGS / f"{time.strftime('%Y%m%d-%H%M%S')}-livekit-{port}.log").open("x")
    process = subprocess.Popen(
        ["livekit-server", "--config-body", config, "--node-ip", "127.0.0.1"],
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    deadline = time.monotonic() + 30
    while True:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
            break
        except OSError:
            if process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError(f"livekit-server did not start; see {log.name}") from None
            time.sleep(0.2)
    yield LiveKitServer(f"ws://127.0.0.1:{port}", key, secret)
    process.terminate()
    process.wait(timeout=10)
    log.close()


@pytest.fixture(scope="module")
def livekit_agent(livekit_server: LiveKitServer) -> Iterator[RunningAgent]:
    yield from _serve(
        "--livekit-url", livekit_server.url, "--room-prefix", PREFIX, env=livekit_server.env
    )


SCENARIO = """\
id: livekit-move
agent: restaurant
trials: 1
max_duration_s: 120
caller:
  persona: "Arjun"
  goal: "Move booking DX7Q2 to Saturday evening"
  voice: male_us_1
  script:
    - "Hi, I need to move my booking to Saturday."
    - "It's D X 7 Q 2."
    - "Anytime between seven and nine is fine."
    - "Seven thirty works."
    - "Yes please."
    - "No, that's all. Thanks, bye."
chaos:
  events:
    - barge_in: {{on: agent_turn, turn: 2, after_s: 0.8, say: "Sorry, it's for Saturday evening."}}
expect:
  state:
    webhook: {verify_url}
    match: {{status: moved, day: saturday, hour: 19, minute: 30}}
  thresholds: {{response_latency_p95_s: 1.5, time_to_yield_p95_s: {yield_limit}}}
"""
# LiveKit carries audio over WebRTC, which adds its own delay in each direction (Opus
# frames and a jitter buffer); a yield takes a round trip. See docs/transports.md.
YIELD_LIMIT_S = 0.8


@needs_server
def test_call_through_a_livekit_room(
    run_cli,
    tmp_path: Path,
    livekit_server: LiveKitServer,
    livekit_agent: RunningAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in livekit_server.env.items():
        monkeypatch.setenv(name, value)
    (tmp_path / "callback.yaml").write_text(
        "targets:\n"
        f"  restaurant: {{transport: livekit, url: '{livekit_server.url}', room_prefix: {PREFIX}}}\n"
    )
    (tmp_path / "scenarios").mkdir()
    (tmp_path / "scenarios" / "move.yaml").write_text(
        SCENARIO.format(
            verify_url=f"http://127.0.0.1:{livekit_agent.port}/verify",
            yield_limit=YIELD_LIMIT_S,
        )
    )

    done = run_cli("run", "scenarios", cwd=tmp_path)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "Exception ignored" not in done.stderr  # the SDK's shutdown noise stays hidden

    run_dir = max((tmp_path / ".callback" / "runs").iterdir())
    results = json.loads((run_dir / "results.json").read_text())
    assert results["provider_models"]["llm"] == "gemini-flash-lite-latest"  # the default
    assert results["provider_models"]["scoring_stt"] == "small"
    [scenario] = results["scenarios"]
    [trial] = scenario["trials"]
    events = trial["call"]["events"]
    assert events[0]["kind"] == "call_start" and events[0]["data"]["transport"] == "livekit"
    assert events[-1]["text"] == "caller_hangup"
    metrics = {m["name"]: m for m in trial["metrics"]}
    assert len(metrics["time_to_yield_p95_s"]["samples"]) == 1  # the agent was heard to stop
    assert metrics["response_latency_p95_s"]["value"] is not None
    assert livekit_agent.verify("livekit-move--t1")["status"] == "moved"

    rooms = asyncio.run(_room_names(livekit_server))
    assert not [r for r in rooms if r.startswith(f"{PREFIX}-")], rooms  # hangup deleted it


async def _room_names(server: LiveKitServer) -> list[str]:
    from livekit import api

    lk = api.LiveKitAPI(server.url.replace("ws://", "http://"), server.key, server.secret)
    try:
        listing = await lk.room.list_rooms(api.ListRoomsRequest())
        return [room.name for room in listing.rooms]
    finally:
        await lk.aclose()


@needs_sdk
async def test_missing_livekit_credentials_are_a_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from callback_voice.transports.build_transport import build_transport

    monkeypatch.delenv("LIVEKIT_API_KEY", raising=False)
    monkeypatch.delenv("LIVEKIT_API_SECRET", raising=False)
    transport = build_transport(LiveKitTarget(url="ws://127.0.0.1:1"))
    with pytest.raises(ConfigError, match="LIVEKIT_API_KEY and LIVEKIT_API_SECRET"):
        await transport.connect("c1")


def test_a_webhook_path_resolves_only_against_a_websocket_agent() -> None:
    ws = WebSocketTarget(url="ws://127.0.0.1:8765/?task_bug=x")
    assert resolve_webhook("/verify", ws) == "http://127.0.0.1:8765/verify"
    with pytest.raises(ConfigError, match="not the agent's"):
        resolve_webhook("/verify", LiveKitTarget(url="ws://127.0.0.1:7880"))


def test_doctor_asks_for_livekit_credentials(
    run_cli, write, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LIVEKIT_API_KEY", raising=False)
    monkeypatch.delenv("LIVEKIT_API_SECRET", raising=False)
    with socket.socket() as server:  # something listening where the LiveKit server would be
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        write(
            "callback.yaml",
            f"targets:\n  lk: {{transport: livekit, url: 'ws://127.0.0.1:{port}'}}\n",
        )
        done = run_cli("doctor")
    assert "LIVEKIT_API_KEY and LIVEKIT_API_SECRET are not set" in done.stdout, done.stdout
