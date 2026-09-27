import os
from pathlib import Path


def model_cache_dir() -> Path:
    """Where downloaded models live, shared across projects.

    ``CALLBACK_MODEL_DIR`` overrides; otherwise ``$XDG_CACHE_HOME/callback`` or
    ``~/.cache/callback``.
    """
    if override := os.environ.get("CALLBACK_MODEL_DIR"):
        return Path(override).expanduser()
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "callback" / "models"
