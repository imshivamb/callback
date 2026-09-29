from urllib.parse import urlsplit, urlunsplit

from callback_voice.core.config.target_config import TargetConfig, WebSocketTarget
from callback_voice.errors import ConfigError


def resolve_webhook(webhook: str, target: TargetConfig) -> str:
    """A full webhook URL, resolving ``/path`` against the target's host and port.

    ``ws://host:8765`` becomes ``http://host:8765/path`` (``wss`` becomes ``https``),
    so a scenario can say ``webhook: /verify`` and follow the agent wherever it runs.
    """
    if not webhook.startswith("/"):
        return webhook
    if not isinstance(target, WebSocketTarget):
        # A LiveKit URL is the media server's, not the agent's; a phone target has none.
        raise ConfigError(
            f"webhook {webhook!r} is a path, but a {target.transport} target's URL "
            "is not the agent's",
            hint="use a full http(s):// webhook URL",
        )
    parts = urlsplit(target.url)
    scheme = {"ws": "http", "wss": "https"}.get(parts.scheme, parts.scheme)
    return str(urlunsplit((scheme, parts.netloc, webhook, "", "")))
