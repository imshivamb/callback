import platform

from callback_voice.doctor.check_result import CheckResult


def check_python_runtime() -> CheckResult:
    """Informational: the package metadata already refuses Python < 3.12."""
    return CheckResult(
        "core", "python", "ok", f"Python {platform.python_version()} on {platform.machine()}"
    )
