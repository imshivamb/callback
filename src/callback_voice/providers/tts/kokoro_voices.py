"""Portable voice aliases so scenarios do not hard-code one engine's voice ids."""

from typing import Final

KOKORO_ALIASES: Final = {
    "female_us_1": "af_heart",
    "female_us_2": "af_bella",
    "male_us_1": "am_michael",
    "male_us_2": "am_fenrir",
    "female_uk_1": "bf_emma",
    "male_uk_1": "bm_george",
    "female_in_1": "hf_alpha",
    "female_in_2": "hf_beta",
    "male_in_1": "hm_omega",
    "male_in_2": "hm_psi",
    "female_es_1": "ef_dora",
    "male_es_1": "em_alex",
}


def kokoro_voice(voice: str | None, default: str) -> str:
    """Resolve an alias (``female_in_1``) or pass a native Kokoro id (``af_heart``) through."""
    if voice is None:
        return default
    return KOKORO_ALIASES.get(voice, voice)


def kokoro_lang(language: str) -> str:
    """Kokoro/espeak language for a scenario language tag.

    Hinglish is written in Latin script, so it is phonemised as English and voiced
    by an Indian voice.
    """
    tag = language.lower()
    if tag in {"hi-en", "hinglish", "en", "en-us"}:
        return "en-us"
    return {
        "en-gb": "en-gb",
        "hi": "hi",
        "es": "es",
        "fr": "fr-fr",
        "it": "it",
        "pt": "pt-br",
        "ja": "ja",
        "zh": "cmn",
    }.get(tag, "en-us")
