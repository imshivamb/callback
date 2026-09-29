"""Helpers shared by the LiveKit transport and the reference agent's LiveKit mode."""

import json
import os
import sys
from urllib.parse import urlsplit, urlunsplit

from livekit import api

from callback_voice.errors import ConfigError

CALLER_IDENTITY = "callback-caller"


def _quiet_ffi_double_drop() -> None:
    """Hide one known LiveKit SDK shutdown error, pass every other one on.

    After a room disconnects, the SDK's native side has already freed some handles;
    when Python later garbage-collects their wrappers (typically at interpreter exit,
    after results are written), ``FfiHandle.__del__`` asserts the second drop
    succeeded and prints a traceback per handle. The call and its results are
    unaffected (livekit 1.1.20).
    """
    hook = sys.unraisablehook

    def filtered(args: "sys.UnraisableHookArgs") -> None:
        owner = getattr(args.object, "__qualname__", "")
        if isinstance(args.exc_value, AssertionError) and owner == "FfiHandle.__del__":
            return
        hook(args)

    sys.unraisablehook = filtered


_quiet_ffi_double_drop()


def room_name(prefix: str, call_id: str) -> str:
    return f"{prefix}-{call_id}"


def room_metadata(call_id: str) -> str:
    """Room metadata an agent can read to tie its end state to the call."""
    return json.dumps({"callback_call_id": call_id})


def http_url(url: str) -> str:
    """The server API's URL: ``ws://host:7880`` -> ``http://host:7880``."""
    parts = urlsplit(url)
    scheme = {"ws": "http", "wss": "https"}.get(parts.scheme, parts.scheme)
    return str(urlunsplit((scheme, parts.netloc, "", "", "")))


def credentials(api_key_env: str, api_secret_env: str) -> tuple[str, str]:
    key, secret = os.environ.get(api_key_env), os.environ.get(api_secret_env)
    missing = [env for env, value in ((api_key_env, key), (api_secret_env, secret)) if not value]
    if missing or key is None or secret is None:
        raise ConfigError(
            f"LiveKit credentials missing: set {' and '.join(missing)}",
            hint="for `livekit-server --dev` the key is devkey and the secret is secret",
        )
    return key, secret


def join_token(key: str, secret: str, identity: str, room: str) -> str:
    return str(
        api.AccessToken(key, secret)
        .with_identity(identity)
        .with_grants(api.VideoGrants(room_join=True, room=room))
        .to_jwt()
    )
