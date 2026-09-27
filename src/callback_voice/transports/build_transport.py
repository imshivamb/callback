from callback_voice.core.config.target_config import TargetConfig, WebSocketTarget
from callback_voice.errors import TransportError
from callback_voice.transports.base import Transport


def build_transport(target: TargetConfig) -> Transport:
    """A fresh, unconnected transport for one call."""
    if isinstance(target, WebSocketTarget):
        from callback_voice.transports.websocket_transport import WebSocketTransport

        return WebSocketTransport(target)
    raise TransportError(
        f"the {target.transport} transport is not implemented yet",
        hint="use a websocket target; LiveKit and Twilio support are planned",
    )
