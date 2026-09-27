from urllib.parse import urlsplit, urlunsplit

from callback_voice.core.config.target_config import TargetConfig
from callback_voice.errors import ConfigError


def resolve_webhook(webhook: str, target: TargetConfig) -> str:
    """A full webhook URL, resolving ``/path`` against the target's host and port.

    ``ws://host:8765`` becomes ``http://host:8765/path`` (``wss`` becomes ``https``),
    so a scenario can say ``webhook: /verify`` and follow the agent wherever it runs.
    """
    if not webhook.startswith("/"):
        return webhook
    url = getattr(target, "url", None)
    if url is None:
        raise ConfigError(
            f"webhook {webhook!r} is a path, but the {target.transport} target has no URL",
            hint="use a full http(s):// webhook URL",
        )
    parts = urlsplit(url)
    scheme = {"ws": "http", "wss": "https"}.get(parts.scheme, parts.scheme)
    return str(urlunsplit((scheme, parts.netloc, webhook, "", "")))
