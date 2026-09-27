from pathlib import Path

import yaml
from pydantic import ValidationError

from callback_voice.core.config.expand_env import expand_env
from callback_voice.core.config.project_config import ProjectConfig
from callback_voice.core.format_validation_error import format_validation_error
from callback_voice.core.load_yaml import load_yaml
from callback_voice.errors import ConfigError

CONFIG_NAME = "callback.yaml"


def find_project_config(start: Path) -> Path | None:
    """Walk up from ``start`` to the filesystem root looking for callback.yaml."""
    current = start.resolve()
    for directory in (current, *current.parents):
        candidate = directory / CONFIG_NAME
        if candidate.is_file():
            return candidate
    return None


def load_project_config(path: Path | None = None, *, start: Path | None = None) -> ProjectConfig:
    """Load callback.yaml from ``path`` or by searching upward from ``start``.

    With no file found, returns defaults rooted at ``start`` so ``validate`` and
    ``doctor`` still work in an empty directory.
    """
    origin = start or Path.cwd()
    config_path = path or find_project_config(origin)
    if config_path is None:
        return ProjectConfig(root=origin.resolve())
    try:
        raw = load_yaml(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot read {config_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{config_path} must be a mapping at the top level")
    try:
        return ProjectConfig.model_validate({**expand_env(raw), "root": config_path.parent})
    except ValidationError as exc:
        raise ConfigError(format_validation_error(exc, config_path)) from exc
