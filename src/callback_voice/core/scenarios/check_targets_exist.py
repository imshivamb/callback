from callback_voice.core.config.project_config import ProjectConfig
from callback_voice.core.models.scenario import Scenario
from callback_voice.errors import ConfigError


def check_targets_exist(scenarios: list[Scenario], config: ProjectConfig) -> None:
    """Every scenario's ``agent`` must name a target in callback.yaml."""
    missing = sorted({s.agent for s in scenarios if s.agent not in config.targets})
    if not missing:
        return
    known = ", ".join(sorted(config.targets)) or "none"
    raise ConfigError(
        f"scenario(s) reference unknown agent(s): {', '.join(missing)} (targets defined: {known})",
        hint="add them under `targets:` in callback.yaml",
    )
