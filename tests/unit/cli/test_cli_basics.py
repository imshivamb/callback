import subprocess
import sys
from pathlib import Path


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "callback_voice.cli", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_version(tmp_path: Path) -> None:
    done = run_cli("--version", cwd=tmp_path)
    assert done.returncode == 0 and done.stdout.startswith("callback ")


def test_doctor_runs_without_keys(tmp_path: Path) -> None:
    done = run_cli("doctor", cwd=tmp_path)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "silero-vad" in done.stdout


def test_validate_exits_2_with_exact_problem(tmp_path: Path) -> None:
    (tmp_path / "bad.yaml").write_text("id: x\nagent: a\ncaller: {persona: p}\n")
    done = run_cli("validate", "bad.yaml", cwd=tmp_path)
    assert done.returncode == 2
    assert "caller.goal" in done.stderr


def test_validate_requires_known_target(tmp_path: Path) -> None:
    (tmp_path / "ok.yaml").write_text("id: x\nagent: nobody\ncaller: {persona: p, goal: g}\n")
    done = run_cli("validate", "ok.yaml", cwd=tmp_path)
    assert done.returncode == 2 and "nobody" in done.stderr
    (tmp_path / "callback.yaml").write_text(
        "targets:\n  nobody: {transport: websocket, url: 'ws://x:1'}\n"
    )
    done = run_cli("validate", "ok.yaml", cwd=tmp_path)
    assert done.returncode == 0, done.stderr
