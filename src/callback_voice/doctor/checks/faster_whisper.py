from importlib.util import find_spec

from callback_voice.core.config.project_config import ProjectConfig
from callback_voice.doctor.check_result import CheckResult

# Approximate download sizes of the CTranslate2 Whisper models (Systran on Hugging Face).
_SIZE_MB = {"tiny": 75, "tiny.en": 75, "base": 145, "base.en": 145, "small": 485, "medium": 1530}
# The bundled reference agent (callback agent serve / callback demo) also uses these.
_AGENT_MODELS = ("base.en", "tiny.en")


def check_faster_whisper(config: ProjectConfig) -> CheckResult:
    """Installed, and which Whisper models are cached vs. downloaded on first use."""
    if find_spec("faster_whisper") is None:
        return CheckResult(
            "local models",
            "faster-whisper",
            "warn",
            "not installed (local STT unavailable)",
            'pip install "callback-voice[local]"',
        )
    from faster_whisper import __version__

    wanted = [
        m
        for m in dict.fromkeys(
            [config.providers.stt.model, config.providers.scoring_stt.model, *_AGENT_MODELS]
        )
        if m
    ]
    cached = [m for m in wanted if _cached(m)]
    missing = [m for m in wanted if m not in cached]
    detail = f"faster-whisper {__version__}; cached: {', '.join(cached) or 'none'}"
    if missing:
        total = sum(_SIZE_MB.get(m, 0) for m in missing)
        detail += f"; first use downloads {', '.join(missing)} (~{total} MB)"
    return CheckResult("local models", "faster-whisper", "ok", detail)


def _cached(model: str) -> bool:
    from huggingface_hub import try_to_load_from_cache

    path = try_to_load_from_cache(f"Systran/faster-whisper-{model}", "model.bin")
    return isinstance(path, str)
