from callback_voice.doctor.check_result import CheckResult


def check_audio_io() -> CheckResult:
    """libsndfile must be able to write WAV (recordings) and MP3 (report audio)."""
    try:
        import soundfile as sf
    except OSError as exc:
        return CheckResult(
            "core", "libsndfile", "fail", str(exc), "pip install --force-reinstall soundfile"
        )
    formats = sf.available_formats()
    if "MP3" not in formats:
        return CheckResult(
            "core",
            "libsndfile",
            "warn",
            f"libsndfile {sf.__libsndfile_version__} cannot encode MP3; reports will embed WAV",
            "Upgrade soundfile to >= 0.12 for bundled MP3 support",
        )
    return CheckResult(
        "core", "libsndfile", "ok", f"libsndfile {sf.__libsndfile_version__} (WAV, MP3)"
    )
