# Connecting Callback to your agent

A target in `callback.yaml` says how Callback reaches the agent under test. Callback
records both sides of every call where it joins the line, so latency and interruption
numbers include whatever the transport itself adds.

## WebSocket

```yaml
targets:
  my-agent:
    transport: websocket
    url: ws://127.0.0.1:8765
    sample_rate: 16000            # of the audio on the wire; 8000–48000
    headers_env: {Authorization: MY_AGENT_TOKEN}   # header -> env var holding its value
```

- **Audio:** binary messages, raw PCM16 little-endian mono at `sample_rate`, both ways.
  Callback sends 20 ms frames in real time; send yours at the pace they should be
  heard (an agent that dumps a whole reply at once cannot stop when interrupted).
- **Control:** text messages carrying JSON. Callback sends `{"type": "hangup"}` before
  closing and `{"type": "dtmf", "digits": "1"}` for keypad input (the tones are also
  played in the audio).
- **Call id:** the `X-Callback-Call-Id` request header, so the agent can tie its end
  state to the call for `expect.state` checks.
- **Ending:** the agent hangs up by closing the socket (code 1000 or 1001); any other
  close is recorded as a lost connection.

## LiveKit

Callback joins a LiveKit room as a participant, the way a caller from a web or phone
client would. It works with a self-hosted open-source LiveKit server.

```bash
pip install "callback-voice[livekit]"
```

```yaml
targets:
  my-agent:
    transport: livekit
    url: ws://127.0.0.1:7880        # the LiveKit server
    room_prefix: callback           # rooms are named <room_prefix>-<call id>
    # agent_identity: my-agent      # listen only to this participant (default: the first with audio)
    # agent_name: my-agent          # dispatch this agent into each room (for workers with explicit dispatch)
    # api_key_env: LIVEKIT_API_KEY  # env vars holding the server's API key and secret
    # api_secret_env: LIVEKIT_API_SECRET
```

For each call Callback creates the room `<room_prefix>-<call id>` (the call id is also
in the room metadata as `{"callback_call_id": "..."}`), joins as `callback-caller`,
publishes its voice as a microphone track, and waits up to 20 s for an agent to join
and publish audio. If none does, the run stops with exit code 2. Hanging up deletes
the room, which disconnects the agent; the agent hangs up by leaving the room.

Your agent has to be sent into these rooms. LiveKit Agents' automatic dispatch (its
default) sends an agent into every new room. A worker registered with an `agent_name`
uses explicit dispatch instead and ignores new rooms: set `agent_name` on the target
and Callback requests that agent in every room it creates. Otherwise have your agent
join rooms with your prefix. The transport has been tested with the bundled reference
agent and with LiveKit's own agent starter, running on a laptop and deployed to LiveKit
Cloud ([RESULTS.md](../RESULTS.md)).

Callback waits 20 s for an agent to join with audio, and that wait is fixed. LiveKit
Cloud's free plan scales an agent to zero between sessions and adds a 10–20 s cold start,
so the first call after an idle spell could time out (exit 2, never a pass). I made a
short warm-up call before each scenario and none of the counted calls timed out.

`expect.state` with a path (`webhook: /verify`) resolves against a WebSocket agent's
URL only. A LiveKit URL belongs to the media server, so give the full URL of your
agent's endpoint instead.

`callback doctor` checks that the server accepts connections and that the key and
secret are set.

### Try it locally with the bundled agent

```bash
brew install livekit                       # or see docs.livekit.io for other systems
livekit-server --dev                       # key devkey, secret secret; port 7880
```

In a second terminal:

```bash
export LIVEKIT_API_KEY=devkey LIVEKIT_API_SECRET=secret
callback agent serve --livekit-url ws://127.0.0.1:7880
```

The reference agent keeps serving WebSocket calls and also answers every new room
named `callback-…` on that server. Then, in your project, point the target at
`ws://127.0.0.1:7880` with `transport: livekit` and run `callback run scenarios` with
the same two variables exported. The development secret is short, so the JWT library
prints an `InsecureKeyLengthWarning`; a production key does not.

### What WebRTC adds

Audio through LiveKit is encoded (Opus) and passes a jitter buffer in each direction,
and Callback measures from its own side of the line, so those delays count. On one
laptop (Apple Silicon, server and agent on the same machine), the same reference agent
process ran the same scripted call three times over each transport:

| | WebSocket | LiveKit |
|---|---|---|
| Reply delay p95, per call | 0.64–0.67 s | 0.79–0.83 s |
| Time to stop when interrupted, per call | 0.49 s (all three) | 0.59–0.65 s |

A tone sent between two participants on that server arrived 55–61 ms later. A reply
delay takes a round trip (the caller's last words in, the agent's first words out), and
so does stopping when interrupted, so expect roughly 0.1–0.2 s more than over a raw
WebSocket, before any network distance. The `callback init` example expects a stop
within 0.6 s; over LiveKit the reference agent sits right at that line. Set limits for
what your callers would experience through your real transport, not the raw socket.
