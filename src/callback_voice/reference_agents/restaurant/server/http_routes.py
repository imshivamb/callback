import json
from http import HTTPStatus
from importlib.resources import files
from typing import Any
from urllib.parse import parse_qs, urlsplit

from websockets.asyncio.server import ServerConnection
from websockets.http11 import Request, Response

from callback_voice.reference_agents.restaurant.server.call_registry import CallRegistry


def make_http_routes(registry: CallRegistry, behavior_name: str) -> Any:
    """Plain-HTTP routes served on the agent's WebSocket port.

    ``GET /verify?call_id=...`` returns the end state of the booking a call touched,
    which is what a scenario's ``expect.state`` checks.
    """

    def route(connection: ServerConnection, request: Request) -> Response | None:
        if request.headers.get("Upgrade", "").lower() == "websocket":
            return None
        url = urlsplit(request.path)
        if url.path == "/health":
            return _json(connection, {"ok": True, "agent": f"restaurant-{behavior_name}"})
        if url.path == "/verify":
            return _verify(connection, registry, parse_qs(url.query))
        if url.path in {"/", "/talk"}:
            page = files("callback_voice.reference_agents.restaurant.server").joinpath(
                "talk_page.html"
            )
            response = connection.respond(HTTPStatus.OK, page.read_text(encoding="utf-8"))
            response.headers["Content-Type"] = "text/html; charset=utf-8"
            return response
        return connection.respond(HTTPStatus.NOT_FOUND, "not found\n")

    return route


def _verify(
    connection: ServerConnection, registry: CallRegistry, query: dict[str, list[str]]
) -> Response:
    call_id = (query.get("call_id") or [""])[0]
    store = registry.get(call_id)
    if store is None:
        return _json(connection, {"error": f"unknown call {call_id!r}"}, HTTPStatus.NOT_FOUND)
    ref = (query.get("booking_ref") or [store.touched or ""])[0]
    booking = store.find(ref) if ref else None
    if booking is None:
        return _json(connection, {"status": "untouched"})
    return _json(connection, booking.to_json())


def _json(
    connection: ServerConnection, body: dict[str, Any], status: HTTPStatus = HTTPStatus.OK
) -> Response:
    response = connection.respond(status, json.dumps(body) + "\n")
    response.headers["Content-Type"] = "application/json"
    return response
