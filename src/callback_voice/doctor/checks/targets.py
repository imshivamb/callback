import asyncio
import os
from urllib.parse import urlsplit

from callback_voice.core.config.project_config import ProjectConfig
from callback_voice.core.config.target_config import LiveKitTarget
from callback_voice.doctor.check_result import CheckResult

_TIMEOUT_S = 1.5


def check_targets(config: ProjectConfig) -> list[CheckResult]:
    """TCP-reachability of every WebSocket and LiveKit target. Phone targets are not dialled."""
    if not config.targets:
        return [CheckResult("targets", "targets", "skip", "no targets in callback.yaml")]
    return [asyncio.run(_check_one(name, target)) for name, target in config.targets.items()]


async def _check_one(name: str, target: object) -> CheckResult:
    transport = getattr(target, "transport", "?")
    url = getattr(target, "url", None)
    if url is None:
        return CheckResult(
            "targets", name, "skip", f"{transport}: not dialled by doctor (costs money)"
        )
    parts = urlsplit(url)
    port = parts.port or (443 if parts.scheme == "wss" else 80)
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(parts.hostname, port), _TIMEOUT_S
        )
    except (OSError, TimeoutError):
        return CheckResult(
            "targets",
            name,
            "warn",
            f"{transport} {url} is not accepting connections",
            "Start the LiveKit server (locally: `livekit-server --dev`)"
            if isinstance(target, LiveKitTarget)
            else "Start the agent (the bundled examples: `callback agent serve`)",
        )
    writer.close()
    await writer.wait_closed()
    if isinstance(target, LiveKitTarget):
        missing = [e for e in (target.api_key_env, target.api_secret_env) if not os.environ.get(e)]
        if missing:
            return CheckResult(
                "targets",
                name,
                "warn",
                f"livekit {url} is reachable, but {' and '.join(missing)} "
                f"{'is' if len(missing) == 1 else 'are'} not set",
                "Callback needs the server's API key and secret to create rooms",
            )
    return CheckResult("targets", name, "ok", f"{transport} {url} is reachable")
