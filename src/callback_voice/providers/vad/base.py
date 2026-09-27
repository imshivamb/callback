from typing import Protocol

from callback_voice.audio.format import Audio


class VoiceActivityModel(Protocol):
    """A stateful frame classifier: feed consecutive windows, get speech probabilities."""

    name: str
    window_samples: int

    def reset(self) -> None:
        """Forget all state before a new, unrelated stream."""
        ...

    def probability(self, window: Audio) -> float:
        """Speech probability for the next ``window_samples`` samples of the stream."""
        ...
