import asyncio
from functools import cache
from typing import Any

from callback_voice.audio.format import Audio
from callback_voice.errors import ProviderUnavailableError
from callback_voice.providers.stt.base import Transcript, Word
from callback_voice.providers.stt.whisper_language import whisper_language


class FasterWhisperStt:
    """Local Whisper via CTranslate2. Free; the model downloads on first use."""

    def __init__(
        self,
        model: str = "base",
        *,
        compute_type: str = "int8",
        words: bool = False,
        beam_size: int = 1,
    ):
        self.name = f"faster-whisper:{model}" + (f"+beam{beam_size}" if beam_size > 1 else "")
        self._model_name = model
        self._compute_type = compute_type
        self._words = words
        self._beam_size = beam_size
        self._lock = asyncio.Lock()

    async def transcribe(self, audio: Audio, *, language: str | None = None) -> Transcript:
        model = await asyncio.to_thread(_load, self._model_name, self._compute_type)
        async with self._lock:  # one decode at a time per model; CTranslate2 is CPU-bound
            return await asyncio.to_thread(self._run, model, audio, whisper_language(language))

    def _run(self, model: Any, audio: Audio, language: str | None) -> Transcript:
        segments, info = model.transcribe(
            audio,
            language=language,
            beam_size=self._beam_size,
            vad_filter=False,
            word_timestamps=self._words,
            condition_on_previous_text=False,
        )
        texts: list[str] = []
        words: list[Word] = []
        for segment in segments:
            texts.append(segment.text.strip())
            for w in segment.words or ():
                words.append(
                    Word(w.word.strip(), float(w.start), float(w.end), float(w.probability))
                )
        return Transcript(" ".join(t for t in texts if t), info.language, tuple(words))


@cache
def _load(model: str, compute_type: str) -> Any:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ProviderUnavailableError(
            "faster-whisper is not installed", hint='pip install "callback-voice[local]"'
        ) from exc
    return WhisperModel(model, device="cpu", compute_type=compute_type)
