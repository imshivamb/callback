from pathlib import Path
from typing import Literal

from pydantic import Field

from callback_voice.core.config.provider_config import ProvidersConfig
from callback_voice.core.config.target_config import TargetConfig
from callback_voice.core.models.strict_model import StrictModel

type RecordedMode = Literal["off", "record", "replay", "auto"]


class ProjectConfig(StrictModel):
    """Parsed ``callback.yaml``.

    ``recorded`` controls the cassette: ``record`` saves caller lines and audio,
    ``replay`` requires them (zero model calls, for CI), ``auto`` replays when a
    cassette exists and records otherwise.
    """

    targets: dict[str, TargetConfig] = Field(default_factory=dict)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    concurrency: int = Field(default=1, ge=1, le=64)
    output_dir: Path = Path(".callback/runs")
    cache_dir: Path = Path(".callback/cache")
    baseline_dir: Path = Path(".callback/baselines")
    cost_cap_usd: float = Field(default=1.0, ge=0)
    recorded: RecordedMode = "auto"
    min_effect: dict[str, float] = Field(default_factory=dict)
    same_turn_pause_s: float = Field(default=0.5, ge=0.0, le=3.0)
    """When the agent pauses and speaks again after the caller took the floor, a pause
    shorter than this is the agent continuing (between sentences), not answering."""
    root: Path = Field(default=Path(), exclude=True)

    def resolve(self, path: Path) -> Path:
        """Resolve a configured path against the directory holding callback.yaml."""
        return path if path.is_absolute() else (self.root / path).resolve()
