"""End-state checks over the phone: the agent never sees Callback's call id, so the
reference agent's /verify finds the call by time (see docs/transports.md)."""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from websockets.asyncio.server import ServerConnection, serve

from callback_voice.core.models.expectation import StateCheck
from callback_voice.errors import CallbackError
from callback_voice.reference_agents.restaurant.server.call_registry import CallRegistry
from callback_voice.reference_agents.restaurant.server.http_routes import make_http_routes
from callback_voice.scoring.verifiers.check_state import check_state


async def _no_calls(ws: ServerConnection) -> None:
    await ws.close()


@asynccontextmanager
async def verify_endpoint(registry: CallRegistry) -> AsyncIterator[str]:
    async with serve(
        _no_calls, "127.0.0.1", 0, process_request=make_http_routes(registry, "good")
    ) as server:
        port = next(iter(server.sockets)).getsockname()[1]
        yield f"http://127.0.0.1:{port}/verify"


def _window(start: float, end: float) -> dict[str, str]:
    return {"call_placed_at": f"{start:.3f}", "call_ended_at": f"{end:.3f}"}


async def test_a_phone_call_is_found_by_time() -> None:
    registry = CallRegistry()
    placed = time.time()
    registry.open("CA-agent-leg")  # what the agent saw: the provider's reference
    async with verify_endpoint(registry) as url, httpx.AsyncClient() as http:
        reply = await http.get(url, params={"call_id": "scn--t1", **_window(placed, time.time())})
    assert reply.status_code == 200
    assert reply.json() == {"status": "untouched", "matched_by": "time"}


async def test_check_state_sends_the_call_details() -> None:
    registry = CallRegistry()
    placed = time.time()
    registry.open("CA-agent-leg")
    async with verify_endpoint(registry) as url:
        result = await check_state(
            StateCheck(webhook=url, match={"status": "untouched"}),
            url,
            call_id="scn--t1",
            scenario_id="scn",
            trial=1,
            call_details={"provider": "twilio", **_window(placed, time.time())},
        )
    assert result.passed, result.detail
    assert result.observed is not None and result.observed["matched_by"] == "time"


async def test_a_call_outside_the_window_is_not_matched() -> None:
    registry = CallRegistry()
    registry.open("CA-earlier")
    later = time.time() + 60
    async with verify_endpoint(registry) as url, httpx.AsyncClient() as http:
        reply = await http.get(url, params={"call_id": "scn--t1", **_window(later, later + 30)})
    assert reply.status_code == 404


async def test_two_calls_in_the_window_are_refused_not_guessed() -> None:
    registry = CallRegistry()
    placed = time.time()
    registry.open("CA-one")
    registry.open("CA-two")
    async with verify_endpoint(registry) as url:
        with pytest.raises(CallbackError, match="409"):
            await check_state(
                StateCheck(webhook=url, match={"status": "untouched"}),
                url,
                call_id="scn--t1",
                scenario_id="scn",
                trial=1,
                call_details=_window(placed, time.time()),
            )


async def test_a_known_call_id_wins_over_the_time() -> None:
    registry = CallRegistry()
    registry.open("scn--t1")
    registry.open("CA-other")
    async with verify_endpoint(registry) as url, httpx.AsyncClient() as http:
        reply = await http.get(url, params={"call_id": "scn--t1", **_window(0, time.time())})
    assert reply.json() == {"status": "untouched"}
