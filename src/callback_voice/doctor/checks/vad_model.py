from callback_voice.doctor.check_result import CheckResult
from callback_voice.errors import CallbackError


def check_vad_model() -> CheckResult:
    """The bundled Silero model must load: every timing metric depends on it."""
    try:
        from callback_voice.providers.vad.silero_vad import SileroVad

        SileroVad()
    except (CallbackError, ImportError, OSError) as exc:
        return CheckResult(
            "core", "silero-vad", "fail", str(exc), "pip install --force-reinstall onnxruntime"
        )
    return CheckResult("core", "silero-vad", "ok", "bundled Silero VAD v5 loads (onnxruntime, CPU)")
