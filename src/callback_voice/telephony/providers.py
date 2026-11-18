"""The phone providers Callback knows. Adding one: a MediaStreamProtocol, a PhoneDialer
and the setup text for its numbers, registered here (see docs/bridges.md)."""

from collections.abc import Callable
from dataclasses import dataclass

from callback_voice.telephony.media_stream import MediaStreamProtocol
from callback_voice.telephony.twilio import TwilioMediaStream, stream_twiml


@dataclass(frozen=True, slots=True)
class PhoneProvider:
    name: str
    protocol: Callable[[], MediaStreamProtocol]
    number_setup: Callable[[str], str]
    """What to configure on a number so its calls stream to the given URL."""


PROVIDERS: dict[str, PhoneProvider] = {
    "twilio": PhoneProvider(
        "twilio",
        TwilioMediaStream,
        lambda url: (
            "Set this TwiML on the number (A call comes in → TwiML Bin):\n" + stream_twiml(url)
        ),
    ),
}
