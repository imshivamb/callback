import os
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from callback_voice.core.config.load_dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]
load_dotenv(REPO)  # the developer's .env (e.g. GEMINI_API_KEY) reaches CLI subprocesses


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class RunningAgent:
    def __init__(self, port: int) -> None:
        self.port = port
        self.url = f"ws://127.0.0.1:{port}"

    def verify(self, call_id: str) -> dict:
        import json

        with urllib.request.urlopen(
            f"http://127.0.0.1:{self.port}/verify?call_id={call_id}", timeout=5
        ) as r:
            return json.loads(r.read())


AGENT_LOGS = REPO / ".callback" / "e2e-agent-logs"


def _serve(*flags: str, env: dict[str, str] | None = None) -> Iterator[RunningAgent]:
    """Start a reference agent with the real `callback agent serve` command.

    The agent writes its own timestamped conversation log (what it heard, said, and
    why it yielded) to ``.callback/e2e-agent-logs/``, one new file per start. Start-up
    errors go to a separate ``*.stderr`` file next to it.
    """
    port = _free_port()
    AGENT_LOGS.mkdir(parents=True, exist_ok=True)
    stderr_path = AGENT_LOGS / f"{time.strftime('%Y%m%d-%H%M%S')}-{port}.stderr"
    stderr_file = stderr_path.open("x")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "callback_voice.cli",
            "agent",
            "serve",
            "--port",
            str(port),
            "--log-dir",
            str(AGENT_LOGS),
            *flags,
        ],
        stdout=subprocess.DEVNULL,
        stderr=stderr_file,
        env={**os.environ, **(env or {})},
    )
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"agent exited during start-up; see {stderr_path}")
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
            break
        except OSError:
            time.sleep(0.5)
    yield RunningAgent(port)
    process.terminate()
    process.wait(timeout=10)
    stderr_file.close()
    if stderr_path.stat().st_size == 0:
        stderr_path.unlink()


@pytest.fixture(scope="session")
def good_agent() -> Iterator[RunningAgent]:
    yield from _serve()


@pytest.fixture(scope="session")
def buggy_agent() -> Iterator[RunningAgent]:
    yield from _serve("--buggy")


@pytest.fixture(scope="session")
def slow_agent() -> Iterator[RunningAgent]:
    """The good agent with 0.4 s added before every reply: an injected latency regression."""
    yield from _serve("--add-latency", "0.4")
