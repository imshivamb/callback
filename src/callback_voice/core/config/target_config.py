from typing import Annotated, Literal

from pydantic import Field

from callback_voice.core.models.strict_model import StrictModel


class WebSocketTarget(StrictModel):
    """An agent that speaks raw PCM16 mono over a WebSocket (see docs/transports.md)."""

    transport: Literal["websocket"] = "websocket"
    url: str = Field(pattern=r"^wss?://")
    sample_rate: int = Field(default=16_000, ge=8_000, le=48_000)
    headers_env: dict[str, str] = Field(
        default_factory=dict,
        description="Header name -> environment variable holding its value",
    )


class LiveKitTarget(StrictModel):
    """An agent that joins a LiveKit room (self-hosted open-source server works)."""

    transport: Literal["livekit"] = "livekit"
    url: str = Field(pattern=r"^wss?://")
    room_prefix: str = "callback"
    agent_identity: str | None = None
    api_key_env: str = "LIVEKIT_API_KEY"
    api_secret_env: str = "LIVEKIT_API_SECRET"


class TwilioTarget(StrictModel):
    """An agent behind a real phone number. Opt-in: costs money per minute."""

    transport: Literal["twilio"] = "twilio"
    to_number: str = Field(pattern=r"^\+[1-9]\d{6,14}$")
    from_number: str = Field(pattern=r"^\+[1-9]\d{6,14}$")
    public_url: str = Field(
        pattern=r"^https://",
        description="Public HTTPS base URL that tunnels to Callback's media-stream server",
    )
    listen_port: int = Field(default=8766, ge=1, le=65535)
    account_sid_env: str = "TWILIO_ACCOUNT_SID"
    auth_token_env: str = "TWILIO_AUTH_TOKEN"
    usd_per_minute: float = Field(default=0.014, ge=0)


type TargetConfig = Annotated[
    WebSocketTarget | LiveKitTarget | TwilioTarget, Field(discriminator="transport")
]
