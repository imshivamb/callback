from callback_voice.core.config.project_config import ProjectConfig
from callback_voice.doctor.check_result import CheckResult
from callback_voice.doctor.checks.api_keys import check_api_keys
from callback_voice.doctor.checks.audio_io import check_audio_io
from callback_voice.doctor.checks.caller_llm import check_caller_llm
from callback_voice.doctor.checks.faster_whisper import check_faster_whisper
from callback_voice.doctor.checks.kokoro import check_kokoro
from callback_voice.doctor.checks.python_runtime import check_python_runtime
from callback_voice.doctor.checks.targets import check_targets
from callback_voice.doctor.checks.vad_model import check_vad_model
from callback_voice.doctor.checks.writable_dirs import check_writable_dirs


def run_checks(config: ProjectConfig) -> list[CheckResult]:
    """Run every doctor check in display order."""
    return [
        check_python_runtime(),
        check_audio_io(),
        check_vad_model(),
        check_writable_dirs(config),
        check_faster_whisper(),
        check_kokoro(),
        check_caller_llm(config.providers.llm),
        *check_api_keys(config.providers),
        *check_targets(config),
    ]
