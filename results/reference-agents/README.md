# Setup: 100 calls to the reference agents

The 100-call run's setup: calls to the bundled restaurant agents, a good one and a
deliberately buggy one, through the same chaos and task scenarios. Its results are
in [`before-2026-09-30/`](before-2026-09-30), the run after fixes is in
[`verification/`](verification), and [`../README.md`](../README.md) compares them.

## What it runs

| Scenarios | Agents | Calls | Caller |
|---|---|---|---|
| Barge-in, backchannel ("mm-hmm"), rough line, silent caller | good and buggy, 5 each | 40 | scripted |
| Move a booking: scripted, move and resize, noisy line | good and buggy, 5 each | 30 | scripted |
| Ignored interruption | buggy agent that ignores interruptions | 10 | scripted |
| Move a booking with an AI caller (persona) | good and buggy, 10 each | 20 | AI (Gemini) |

- Scenarios are copies of the ones in [`scenarios/`](../../scenarios), with the agent
  and number of calls set per file.
- The AI caller is pinned to `gemini-3.5-flash-lite`; `results.json` records the
  exact model of every provider under `provider_models`. Speech recognition, voices
  and both agents run locally.
- One call at a time (`concurrency: 1`): parallel calls on one machine add latency.

## Run it yourself

```bash
callback agent serve                        # good agent, port 8765
callback agent serve --buggy --port 8766    # buggy agent, port 8766 (another terminal)
cd results/reference-agents
callback run scenarios
```

The AI caller needs `GEMINI_API_KEY`. The first run records its lines; later runs
replay them without calling the model. Expect about three hours on a laptop.
