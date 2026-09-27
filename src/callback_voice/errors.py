"""Error hierarchy.

Every error Callback raises on purpose derives from ``CallbackError``. The CLI maps
all of them to exit code 2 (config or runtime error), so a broken run can never be
reported as a pass.
"""


class CallbackError(Exception):
    """Base class for expected, user-facing failures."""

    hint: str | None = None

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        if hint is not None:
            self.hint = hint


class ConfigError(CallbackError):
    """``callback.yaml`` is missing, malformed or references something unknown."""


class ScenarioError(CallbackError):
    """A scenario file failed to parse or validate."""


class TransportError(CallbackError):
    """The agent under test could not be reached or dropped the call unexpectedly."""


class ProviderError(CallbackError):
    """An STT, TTS, LLM or VAD provider failed."""


class ProviderUnavailableError(ProviderError):
    """A provider's optional dependency or model is not installed."""
