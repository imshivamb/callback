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


@pytest.fixture(scope="session")
def good_agent() -> Iterator[RunningAgent]:
    """The good reference agent, started with the real `callback agent serve` command."""
    port = _free_port()
    process = subprocess.Popen(
        [sys.executable, "-m", "callback_voice.cli", "agent", "serve", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env=os.environ.copy(),
    )
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"agent exited: {process.stderr.read().decode() if process.stderr else ''}"
            )
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
            break
        except OSError:
            time.sleep(0.5)
    yield RunningAgent(port)
    process.terminate()
    process.wait(timeout=10)
