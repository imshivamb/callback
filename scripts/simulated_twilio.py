"""A simulated Twilio on this machine, for testing phone calls end to end at no cost.

It answers the REST call Callback makes to place a call, then plays the phone network:
it connects Callback's media stream to the stream of the number being called (for
example `callback agent phone-bridge` in front of a reference agent) and relays audio
both ways, with an optional one-way delay. With --trial it imitates a Twilio trial
account: before connecting, it plays a message to the called side and waits for the
key 1 as a tone, as a real trial call does.

    python scripts/simulated_twilio.py --number ws://127.0.0.1:8767/stream/TOKEN \\
        --callback-port 8766 [--port 8790] [--delay-ms 100] [--trial]

Then run Callback with CALLBACK_TWILIO_API_BASE=http://127.0.0.1:8790/2010-04-01 and
any TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN. Not a full Twilio: only what Callback uses.
"""

import argparse
import asyncio
import base64
import contextlib
import json
import re
import secrets
from urllib.parse import parse_qs

import numpy as np
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from callback_voice.audio.mulaw import mulaw_decode, mulaw_encode

RATE = 8_000


def start(stream_sid: str, call_sid: str, params: dict[str, str]) -> str:
    body = {"streamSid": stream_sid, "callSid": call_sid, "customParameters": params}
    return json.dumps({"event": "start", "streamSid": stream_sid, "start": body})


def media(stream_sid: str, audio: np.ndarray) -> str:
    payload = base64.b64encode(mulaw_encode(audio.astype(np.float32))).decode()
    body = {"track": "inbound", "payload": payload}
    return json.dumps({"event": "media", "streamSid": stream_sid, "media": body})


def stop(stream_sid: str) -> str:
    return json.dumps({"event": "stop", "streamSid": stream_sid})


def audio_of(message: str | bytes) -> np.ndarray | None:
    event = json.loads(message)
    if event.get("event") != "media":
        return None
    return mulaw_decode(base64.b64decode(event["media"]["payload"]))


def has_key_1(audio: np.ndarray) -> bool:
    """Goertzel check for DTMF 1 (697 Hz + 1209 Hz) against the strongest other row/column."""
    if len(audio) < 160:
        return False

    def power(hz: float) -> float:
        k = 2 * np.cos(2 * np.pi * hz / RATE)
        s1 = s2 = 0.0
        for x in audio[-400:]:
            s1, s2 = float(x) + k * s1 - s2, s1
        return float(s1 * s1 + s2 * s2 - k * s1 * s2)

    rows = [power(f) for f in (697, 770, 852, 941)]
    cols = [power(f) for f in (1209, 1336, 1477)]
    return (
        rows[0] > 1.0
        and rows[0] > 4 * max(rows[1:])
        and cols[0] > 1.0
        and cols[0] > 4 * max(cols[1:])
    )


class Network:
    def __init__(self, number_url: str, callback_port: int, delay_s: float, trial: bool) -> None:
        self.number_url = number_url
        self.callback_port = callback_port
        self.delay_s = delay_s
        self.trial = trial
        self.calls: dict[str, asyncio.Event] = {}

    def place(self, twiml: str) -> str:
        found = re.search(r'Stream url="wss://[^/"]+(/[^"]*)"', twiml)
        params = dict(re.findall(r'<Parameter name="([^"]+)" value="([^"]*)"', twiml))
        if found is None:
            raise ValueError("no <Stream url=...> in the TwiML")
        call_sid = "CA" + secrets.token_hex(16)
        self.calls[call_sid] = asyncio.Event()
        url = f"ws://127.0.0.1:{self.callback_port}{found.group(1)}"
        asyncio.get_running_loop().create_task(self._call(call_sid, url, params))
        return call_sid

    def hang_up(self, call_sid: str) -> None:
        if call_sid in self.calls:
            self.calls[call_sid].set()

    async def _call(self, call_sid: str, callback_url: str, params: dict[str, str]) -> None:
        ended = self.calls[call_sid]
        async with connect(self.number_url, max_queue=None) as number:
            await number.send(start("MZ-number", call_sid + "-in", {}))
            if self.trial and not await self._trial_gate(number):
                print(f"{call_sid}: no key pressed; trial call dropped")
                return
            async with connect(callback_url, max_queue=None) as caller:
                await caller.send(start("MZ-caller", call_sid, params))
                print(f"{call_sid}: connected")
                legs = [
                    asyncio.create_task(self._pipe(caller, number, "MZ-number")),
                    asyncio.create_task(self._pipe(number, caller, "MZ-caller")),
                    asyncio.create_task(ended.wait()),
                ]
                await asyncio.wait(legs, return_when=asyncio.FIRST_COMPLETED)
                for leg in legs:
                    leg.cancel()
                for ws, sid in ((caller, "MZ-caller"), (number, "MZ-number")):
                    with contextlib.suppress(ConnectionClosed):
                        await ws.send(stop(sid))
                        await ws.close()
        print(f"{call_sid}: ended")

    async def _trial_gate(self, number: ClientConnection) -> bool:
        """Play a trial-style message (a tone pattern) and wait up to 20 s for key 1."""
        message = 0.2 * np.sin(2 * np.pi * 400 * np.arange(RATE * 6) / RATE)
        for i in range(0, len(message), 160):
            await number.send(media("MZ-number", message[i : i + 160]))
            await asyncio.sleep(0.02)
        heard = np.zeros(0, dtype=np.float32)
        with contextlib.suppress(TimeoutError, ConnectionClosed):
            async with asyncio.timeout(20):
                async for reply in number:
                    if (audio := audio_of(reply)) is not None:
                        heard = np.concatenate([heard, audio])[-800:]
                        if has_key_1(heard):
                            print("trial gate: key 1 heard")
                            return True
        return False

    async def _pipe(self, source: ClientConnection, sink: ClientConnection, sid: str) -> None:
        with contextlib.suppress(ConnectionClosed):
            async for message in source:
                if (audio := audio_of(message)) is None:
                    continue
                if self.delay_s:
                    await asyncio.sleep(self.delay_s)
                await sink.send(media(sid, audio))


async def serve_rest(network: Network, port: int) -> None:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        head = (await reader.readuntil(b"\r\n\r\n")).decode()
        request_line, *header_lines = head.split("\r\n")
        _, path, _ = request_line.split(" ", 2)
        headers = {
            k.lower(): v.strip() for k, _, v in (h.partition(":") for h in header_lines if h)
        }
        body = (await reader.readexactly(int(headers.get("content-length", "0")))).decode()
        form = {k: v[0] for k, v in parse_qs(body).items()}
        status, reply = 404, {"message": "not found"}
        if path.endswith("/Calls.json"):
            sid = network.place(form.get("Twiml", ""))
            print(f"call placed to {form.get('To')} from {form.get('From')}: {sid}")
            status, reply = 201, {"sid": sid, "status": "queued"}
        elif m := re.search(r"/Calls/([^/]+)\.json$", path):
            network.hang_up(m.group(1))
            status, reply = 200, {"sid": m.group(1), "status": "completed"}
        data = json.dumps(reply).encode()
        writer.write(
            f"HTTP/1.1 {status} OK\r\nContent-Type: application/json\r\n"
            f"Content-Length: {len(data)}\r\nConnection: close\r\n\r\n".encode()
            + data
        )
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", port)
    print(f"simulated Twilio API on http://127.0.0.1:{port}/2010-04-01")
    async with server:
        await server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--number", required=True, help="ws:// URL the called number streams to")
    parser.add_argument("--callback-port", type=int, required=True, help="Callback's listen_port")
    parser.add_argument("--port", type=int, default=8790, help="port for the simulated REST API")
    parser.add_argument("--delay-ms", type=float, default=0.0, help="one-way network delay")
    parser.add_argument("--trial", action="store_true", help="imitate a trial account's key gate")
    args = parser.parse_args()
    network = Network(args.number, args.callback_port, args.delay_ms / 1000, args.trial)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(serve_rest(network, args.port))


if __name__ == "__main__":
    main()
