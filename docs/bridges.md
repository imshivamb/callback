# Writing your own bridge

A bridge (a transport) is how Callback reaches an agent: it dials or joins, moves
audio both ways, and hangs up. Everything else, the caller, chaos, recording and
scoring, stays the same. If your agent speaks a protocol Callback does not have yet,
this page is what you write.

The existing ones are the examples to copy, in `src/callback_voice/transports/`:

| File | Lines | Reaches |
|---|---|---|
| `websocket_transport.py` | 94 | raw PCM16 over a WebSocket; the smallest one |
| `livekit_transport.py` + `livekit_room.py` | 171 + 71 | a LiveKit room |
| `phone_transport.py` | 141 | a phone number, through any provider with a media-stream API |

## The interface

Subclass `Transport` from `transports/base.py`:

```python
class MyTransport(Transport):
    name = "my-platform"

    async def connect(self, call_id: str) -> None: ...
    async def send_audio(self, audio: Audio) -> None: ...
    async def hangup(self) -> None: ...
    async def send_dtmf(self, digits: str) -> bool: ...   # optional
```

- **`connect(call_id)`**: dial or join, and return once audio can flow. Raise
  `TransportError` with a `hint` when it cannot; the run then exits 2, never passes.
  Pass `call_id` to the agent if you can (a header, metadata, a parameter), so its end
  state can be checked against the call.
- **`send_audio(audio)`**: called every 20 ms with one frame of caller audio, 320
  samples of float32 mono at 16 kHz. Convert it to the wire format and send it. Do not
  buffer and burst: the agent must hear it in real time.
- **Agent audio in**: put each chunk you receive on `self.inbound` as float32 mono at
  16 kHz. Any length works; the engine drains the queue on its own 20 ms clock.
- **`hangup()`**: end the call from the caller's side. It must be safe to call twice
  and after the agent has already hung up. Call `self.mark_closed("caller_hangup")`.
- **When the agent ends the call**, call `self.mark_closed("agent_hangup")`; for a
  broken connection, `self.mark_closed("connection_lost (...)")`.
- **`send_dtmf(digits)`**: return `True` if you sent the digits out of band. Return
  `False` (the default) and the caller plays the tones in the audio instead.

## Adding a phone provider

Phone calls are already provider-neutral: `PhoneTransport` (placing calls) and
`callback agent phone-bridge` (putting a WebSocket agent behind a number) take the
provider as two small pieces, in `src/callback_voice/telephony/`. Twilio is
`telephony/twilio.py`, 142 lines. A new provider (Telnyx, Plivo, Vonage, ...) is:

- **A `MediaStreamProtocol`** (`telephony/media_stream.py`): `parse` turns one of the
  provider's stream messages into a `StreamEvent` (`start`, `media` with decoded
  audio, `dtmf`, `stop`), and `media` builds one outbound audio message. Set
  `sample_rate` to the stream's rate; resampling and pacing are shared.
- **A `PhoneDialer`** (`telephony/dialer.py`): `check_credentials`, `place_call`
  (dial a number and have its audio streamed to a URL) and `end_call`. Credentials
  come only from environment variables.
- **An entry in `telephony/providers.py`**: the protocol, and the text that tells a
  user what to set on a number so its calls stream to the bridge.
- **A target** in `core/config/target_config.py` and a branch in `build_transport`
  that builds `PhoneTransport(protocol, dialer, ...)`.

The warning before calls, the cost estimate and cap, one call at a time, the stream
token and hanging up are shared, so a new provider gets them for free. The tests in
`tests/e2e/test_phone_transport.py` and `test_phone_bridge.py` already run every
case against two providers (Twilio and an invented one, in `tests/e2e/phone_fakes.py`):
add a `Wire` for the new provider to `WIRES` and they cover it too.

A hosted platform whose agent has a phone number (many do) can be called this way
already, with no new code.

## Audio conversion

- **Sample rate:** use `StreamResampler(from_rate, to_rate)` from
  `audio/stream_resampler.py`, one per direction. It resamples a live stream in chunks
  without clicks.
- **PCM16:** `audio/pcm.py` has `to_pcm16` and `from_pcm16`.
- **G.711 mu-law** (phone networks): `audio/mulaw.py` has `mulaw_encode` and
  `mulaw_decode`.

## Wiring it in

1. **A target model** in `core/config/target_config.py`, with a
   `transport: Literal["my-platform"]` field, added to the `TargetConfig` union. Keep
   secrets out of it: name the environment variables that hold them (`*_env` fields).
2. **`build_transport`** in `transports/build_transport.py` returns your class for that
   target. Import optional SDKs inside the branch and turn an `ImportError` into a
   `TransportError` that says which extra to install.
3. **`callback doctor`** (`doctor/checks/targets.py`): check what can be checked
   without placing a paid call, such as reachability and credentials.
4. **Docs:** a section in [transports.md](transports.md) with the config, what happens
   on each call, and what the transport adds to the numbers.

## Testing it

Test against a fake of the other side, so the tests run offline and cost nothing.
`tests/e2e/test_twilio.py` fakes Twilio's REST API with `httpx.MockTransport` and plays
the phone end of the media stream itself. Check at least that:

- a call connects and audio flows both ways;
- the agent hanging up ends the call with `agent_hangup`;
- `hangup()` ends it on the other side too;
- a refused or unanswered call raises `TransportError` and leaves nothing running.

Then run one real call, and compare Callback's timings with the recording before you
trust the numbers.
