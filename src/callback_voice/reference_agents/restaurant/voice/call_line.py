from collections.abc import AsyncIterator
from typing import Protocol


class CallLine(Protocol):
    """The agent's end of a call: PCM16 16 kHz mono frames in and out.

    A WebSocket connection is one as it is (binary messages are audio, a text message
    containing ``"hangup"`` ends the call); a LiveKit room is wrapped in one.
    """

    def __aiter__(self) -> AsyncIterator[bytes | str]: ...

    async def send(self, message: bytes) -> None: ...

    async def close(self) -> None: ...
