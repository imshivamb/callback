from pathlib import Path

from callback_voice.core.baseline.save_baseline import baseline_path
from callback_voice.core.models.baseline import Baseline
from callback_voice.errors import ConfigError


def load_baseline(baseline_dir: Path, name: str) -> Baseline:
    path = baseline_path(baseline_dir, name)
    if not path.is_file():
        saved = sorted(p.stem for p in baseline_dir.glob("*.json"))
        raise ConfigError(
            f"no baseline {name!r} in {baseline_dir}",
            hint=f"saved: {', '.join(saved)}"
            if saved
            else "save one with `callback baseline save NAME`",
        )
    return Baseline.model_validate_json(path.read_text(encoding="utf-8"))
