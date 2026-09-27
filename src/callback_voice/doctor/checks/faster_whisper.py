from importlib.util import find_spec

from callback_voice.doctor.check_result import CheckResult


def check_faster_whisper() -> CheckResult:
    if find_spec("faster_whisper") is None:
        return CheckResult(
            "local models",
            "faster-whisper",
            "warn",
            "not installed (local STT unavailable)",
            'pip install "callback-voice[local]"',
        )
    from faster_whisper import __version__

    return CheckResult(
        "local models",
        "faster-whisper",
        "ok",
        f"faster-whisper {__version__}; models download on first use (~150 MB for base)",
    )
