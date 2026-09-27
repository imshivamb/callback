from pathlib import Path

import pytest

from callback_voice.core.config.load_project_config import load_project_config
from callback_voice.core.config.target_config import WebSocketTarget
from callback_voice.errors import ConfigError


def test_defaults_without_file(tmp_path: Path) -> None:
    config = load_project_config(start=tmp_path)
    assert config.providers.tts.name == "kokoro"
    assert config.concurrency == 1 and config.cost_cap_usd == 1.0
    assert config.resolve(config.output_dir) == tmp_path.resolve() / ".callback/runs"


def test_found_by_walking_up_and_env_expanded(tmp_path: Path, write_yaml, monkeypatch) -> None:
    monkeypatch.setenv("AGENT_HOST", "agent.internal")
    write_yaml(
        "callback.yaml",
        "targets:\n  bot: {transport: websocket, url: 'ws://${AGENT_HOST}:${PORT:-8765}'}\n",
    )
    nested = tmp_path / "scenarios" / "deep"
    nested.mkdir(parents=True)
    config = load_project_config(start=nested)
    target = config.targets["bot"]
    assert isinstance(target, WebSocketTarget)
    assert target.url == "ws://agent.internal:8765"
    assert config.root == tmp_path


def test_invalid_transport_names_the_field(write_yaml) -> None:
    path = write_yaml("callback.yaml", "targets:\n  bot: {transport: carrier-pigeon}\n")
    with pytest.raises(ConfigError, match=r"targets\.bot"):
        load_project_config(path)
