from callback_voice.core.config.target_config import (
    LiveKitTarget,
    TargetConfig,
    TwilioTarget,
    WebSocketTarget,
)
from callback_voice.errors import TransportError
from callback_voice.transports.base import Transport


def build_transport(target: TargetConfig) -> Transport:
    """A fresh, unconnected transport for one call."""
    if isinstance(target, WebSocketTarget):
        from callback_voice.transports.websocket_transport import WebSocketTransport

        return WebSocketTransport(target)
    if isinstance(target, LiveKitTarget):
        try:
            from callback_voice.transports.livekit_transport import LiveKitTransport
        except ImportError as exc:
            raise TransportError(
                "the livekit transport needs the LiveKit SDK",
                hint='pip install "callback-voice[livekit]"',
            ) from exc
        return LiveKitTransport(target)
    if isinstance(target, TwilioTarget):
        from callback_voice.transports.twilio_transport import TwilioTransport

        return TwilioTransport(target)
    raise TransportError(f"unknown transport {getattr(target, 'transport', '?')}")
