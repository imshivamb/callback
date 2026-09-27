import tempfile

from callback_voice.core.config.project_config import ProjectConfig
from callback_voice.doctor.check_result import CheckResult


def check_writable_dirs(config: ProjectConfig) -> CheckResult:
    """Runs, caches and baselines must be writable."""
    for path in (config.output_dir, config.cache_dir, config.baseline_dir):
        directory = config.resolve(path)
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=directory):
                pass
        except OSError as exc:
            return CheckResult("core", "output dirs", "fail", f"{directory}: {exc.strerror}")
    return CheckResult(
        "core", "output dirs", "ok", f"writing under {config.resolve(config.output_dir).parent}"
    )
