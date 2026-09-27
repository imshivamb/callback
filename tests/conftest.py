import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

type RunCli = Callable[..., subprocess.CompletedProcess[str]]


@pytest.fixture
def run_cli(tmp_path: Path) -> RunCli:
    """Run the real `callback` CLI in a fresh project directory."""

    def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "callback_voice.cli", *args],
            cwd=cwd or tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )

    return _run


@pytest.fixture
def write(tmp_path: Path) -> Callable[[str, str], Path]:
    def _write(name: str, body: str) -> Path:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    return _write
