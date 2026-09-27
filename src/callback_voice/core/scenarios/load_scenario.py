from pathlib import Path

import yaml
from pydantic import ValidationError

from callback_voice.core.format_validation_error import format_validation_error
from callback_voice.core.load_yaml import load_yaml
from callback_voice.core.models.scenario import Scenario
from callback_voice.errors import ScenarioError


def load_scenario(path: Path) -> Scenario:
    """Parse and validate one scenario file, raising ``ScenarioError`` with exact locations."""
    try:
        raw = load_yaml(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ScenarioError(f"cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ScenarioError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ScenarioError(f"{path} must be a mapping with id, agent, caller, ...")
    try:
        return Scenario.model_validate({**raw, "source": path})
    except ValidationError as exc:
        raise ScenarioError(format_validation_error(exc, path)) from exc
