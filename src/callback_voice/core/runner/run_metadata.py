import hashlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from callback_voice.core.config.project_config import ProjectConfig


def new_run_id(now: datetime | None = None) -> str:
    """Sortable, human-readable run id: ``20260927-131502``."""
    return (now or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")


def git_sha(directory: Path) -> str | None:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() or None


def agent_config_hash(project: ProjectConfig) -> str:
    """Fingerprint of targets and providers, so results show when the setup changed."""
    material = project.model_dump_json(include={"targets", "providers"})
    return hashlib.sha256(material.encode()).hexdigest()[:12]
