from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np

from callback_voice.audio.format import SAMPLE_RATE
from callback_voice.core.config.project_config import ProjectConfig, RecordedMode
from callback_voice.core.config.provider_config import ProviderChoice
from callback_voice.core.models.scenario import Scenario
from callback_voice.providers.llm.base import ChatModel
from callback_voice.providers.llm.build_llm import build_llm
from callback_voice.providers.stt.base import SpeechToText
from callback_voice.providers.stt.build_stt import build_stt
from callback_voice.providers.tts.build_tts import build_tts
from callback_voice.providers.tts.cached_tts import CachedTts
from callback_voice.providers.vad.base import VoiceActivityModel
from callback_voice.providers.vad.build_vad import build_vad


@dataclass
class Runtime:
    """Providers for one ``callback run``, built lazily so a scripted-only run never
    loads an LLM client or an STT model."""

    project: ProjectConfig
    recorded: RecordedMode
    llm_choice: ProviderChoice

    @cached_property
    def tts(self) -> CachedTts:
        return CachedTts(
            build_tts(self.project.providers.tts),
            self.project.resolve(self.project.cache_dir) / "tts",
        )

    @cached_property
    def stt(self) -> SpeechToText:
        return build_stt(self.project.providers.stt)

    @cached_property
    def llm(self) -> ChatModel:
        return build_llm(self.llm_choice)

    async def warm_up(self, scenarios: list[Scenario]) -> None:
        """Load models before the first call so the caller's first turn is not slowed
        by a one-off model load (which the agent would hear as dead air)."""
        voices = {(s.caller.voice, s.caller.language) for s in scenarios}
        for voice, language in voices:
            await self.tts.synthesize("Hello.", voice=voice, language=language)
        if any(s.caller.script is None for s in scenarios) and self.recorded != "replay":
            await self.stt.transcribe(np.zeros(SAMPLE_RATE // 2, dtype=np.float32), language="en")

    @property
    def make_vad(self) -> Callable[[], VoiceActivityModel]:
        return lambda: build_vad(self.project.providers.vad)

    @property
    def cassette_dir(self) -> Path:
        return self.project.resolve(self.project.cache_dir) / "cassettes"
