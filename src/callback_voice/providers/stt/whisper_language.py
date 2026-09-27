def whisper_language(language: str | None) -> str | None:
    """Map a scenario language tag to a Whisper language code.

    Code-switched ``hi-en`` (Hinglish) is decoded as English so the transcript stays
    in Latin script, which is how callers and scenario entities are written.
    """
    if language is None:
        return None
    primary = language.lower().split("-")[0]
    return "en" if language.lower() in {"hi-en", "hinglish"} else primary
