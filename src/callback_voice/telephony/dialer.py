from abc import ABC, abstractmethod


class PhoneDialer(ABC):
    """A phone provider's call control: place an outbound call that streams to a URL.

    Implementations read their credentials from the environment and raise
    ``TransportError`` (with a hint) when they cannot place the call.
    """

    name: str

    @abstractmethod
    def check_credentials(self) -> None:
        """Raise ``TransportError`` if the credentials are missing. Makes no request."""

    @abstractmethod
    async def place_call(
        self, to_number: str, from_number: str, stream_url: str, call_id: str
    ) -> str:
        """Dial ``to_number``; once answered the provider streams the call to ``stream_url``.
        Returns the provider's reference for the call."""

    @abstractmethod
    async def end_call(self, call_ref: str) -> None:
        """Hang up. Must not raise if the call has already ended."""

    async def close(self) -> None:  # noqa: B027 - optional hook, a no-op by default
        """Release connections. Called once, after the call."""
