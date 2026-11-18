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
    which is what a scenario's ``expect.state`` checks. For a phone call the agent never
    sees Callback's call id; with ``call_placed_at`` and ``call_ended_at`` (sent by
    Callback for phone targets) it finds the one call that began in that time.
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
    matched_by = "call_id"
    if store is None and (window := _call_window(query)) is not None:
        # A phone call: the agent saw the provider's reference, not Callback's id, so
        # find the one call that began while Callback's call was up.
        found = registry.opened_between(*window)
        if len(found) > 1:
            return _json(
                connection,
                {"error": f"{len(found)} calls began in that time; cannot tell which"},
                HTTPStatus.CONFLICT,
            )
        if found:
            store, matched_by = registry.get(found[0]), "time"
    if store is None:
        return _json(connection, {"error": f"unknown call {call_id!r}"}, HTTPStatus.NOT_FOUND)
    ref = (query.get("booking_ref") or [store.touched or ""])[0]
    booking = store.find(ref) if ref else None
    body = {"status": "untouched"} if booking is None else booking.to_json()
    if matched_by != "call_id":
        body["matched_by"] = matched_by
    return _json(connection, body)


def _call_window(query: dict[str, list[str]]) -> tuple[float, float] | None:
    try:
        return float(query["call_placed_at"][0]), float(query["call_ended_at"][0])
    except (KeyError, IndexError, ValueError):
        return None


def _json(
    connection: ServerConnection, body: dict[str, Any], status: HTTPStatus = HTTPStatus.OK
) -> Response:
    response = connection.respond(status, json.dumps(body) + "\n")
    response.headers["Content-Type"] = "application/json"
    return response
