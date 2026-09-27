from importlib.util import find_spec

from callback_voice.doctor.check_result import CheckResult


def check_kokoro() -> CheckResult:
    """Kokoro needs the kokoro-onnx package plus a working espeak-ng library."""
    if find_spec("kokoro_onnx") is None:
        return CheckResult(
            "local models",
            "kokoro-tts",
            "warn",
            "not installed (local TTS unavailable)",
            'pip install "callback-voice[local]"',
        )
    from callback_voice.providers.tts.find_espeak import find_espeak

    espeak = find_espeak()
    if espeak is None:
        return CheckResult(
            "local models",
            "kokoro-tts",
            "warn",
            "kokoro-onnx installed but no working espeak-ng found",
            "brew install espeak-ng  (macOS)  |  apt install espeak-ng  (Debian/Ubuntu)",
        )
    from callback_voice.providers.tts.kokoro_files import kokoro_files_present

    cached = "model cached" if kokoro_files_present() else "model downloads on first use (~200 MB)"
    return CheckResult(
        "local models", "kokoro-tts", "ok", f"espeak-ng at {espeak.library}; {cached}"
    )
