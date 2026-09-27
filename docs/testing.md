# Testing Callback yourself

Everything below runs locally. The only thing that may call the internet is the
simulated caller's LLM (Gemini free tier) and one-time model downloads.


## 1. One-time setup

```bash
brew install uv espeak-ng          # espeak-ng is needed by the Kokoro voice (macOS)
cd ~/Projects/AI/Callback
uv sync --extra local              # Python 3.12 venv + local speech models' packages
```

Put your Gemini key in `.env` at the repo root (already git-ignored):

```bash
GEMINI_API_KEY=your-key-here
```

Callback loads the nearest `.env` automatically; variables already exported in
your shell take precedence.

Check the environment:

```bash
uv run callback doctor
```

Everything under **CORE** must be green. Under **LOCAL MODELS**, faster-whisper
and kokoro should be green (models download on first use, ~350 MB total, into
`~/.cache/callback` and `~/.cache/huggingface`). **CALLER LLM** should say
`gemini-flash-lite-latest ready`.

## 2. Talk to the reference agent yourself

```bash
uv run callback agent serve -v            # the good agent, port 8765
uv run callback agent serve --buggy -v --port 8766   # the buggy copy
```

Open <http://127.0.0.1:8765> in Chrome, click **Start call**, and use headphones.
Try: *"Hi, I need to move my booking"* then *"D X 7 Q 2"* then *"Saturday, seven
thirty"*. Interrupt it mid-sentence; say "mm-hmm" while it talks. With `-v` the
terminal prints what the agent heard and said.

Every start of the agent also writes a new log file, never overwritten:
`.callback/agent-logs/<YYYYmmdd-HHMMSS>-<good|buggy>-<port>.log`. It records what
the agent heard and said and why it stopped talking (e.g. `not a backchannel:
'Amen.'`), with dated, millisecond timestamps. The path is printed at start-up.
Agents started by the E2E tests log to `.callback/e2e-agent-logs/`.

After a browser call you can check what the agent actually did to the booking:
`curl http://127.0.0.1:8765/verify?call_id=<id>` (the id is printed in the log).

## 3. Run scenarios the way a user would

Terminal 1, the agent under test:

```bash
uv run callback agent serve -v
```

Terminal 2, validate then run:

```bash
uv run callback validate scenarios
uv run callback run scenarios/restaurant/move-booking-scripted.yaml   # no LLM
uv run callback run scenarios/restaurant/move-booking-persona.yaml    # Gemini caller
echo $?    # 0 pass, 1 fail, 2 error
```

What to look at afterwards (newest run first):

```bash
ls -t .callback/runs | head -1
```

Each run folder has `report.html`, `results.json`, `junit.xml` and one folder per call
under `calls/` with:

| File | What it is |
|---|---|
| `call.wav` | Stereo recording: **left = caller**, **right = agent**, one shared clock |
| `caller_clean.wav` | The caller's voice without chaos (noise, packet loss) |
| `events.jsonl` | Every caller line, agent turn, chaos action, with timings |

### The report

`report.html` is a single file: the data and every call's audio (as MP3, about 270 KB
a minute) are inside it, so it opens offline and can be attached to a pull request.
From the top:

1. **The verdict and one sentence** saying what went wrong, e.g. "The agent keeps
   talking when the caller interrupts (1.16 s vs 0.6 s) and replies too slowly (2.24 s
   vs a 1.5 s limit)." It is written from the numbers, the same way every time.
2. **Up to three problem tiles**, most serious first, each with **▶ Hear it**, which
   opens the call at that moment and plays it.
3. **The call**: caller and agent waveforms on one time axis, an Events row (amber ◆
   for disturbances Callback caused, red ▼ for problems), a "Wait before reply" bar per
   answer against the dashed limit, and a whole-call strip to move around. Below it,
   the problems in that call; repeats are grouped ("Slow reply ×6") with a chip per
   occurrence.
4. **Details** (folded): every number across calls with its 95% range and limit, and
   what the terms mean. The ⓘ next to a term explains it on hover or keyboard focus.

| Do | See |
|---|---|
| Click a problem or a time chip, or press `N` / `P` | Plays from just before it; the playhead moves over both waveforms |
| Hover a pin, a speech block, a chaos diamond or a bar | One sentence on what happened there |
| `1` / `2` / `3` | Hear both sides, only the caller, or only the agent |
| `+` / `-` / `0`, or drag the whole-call strip | Zoom and move along the call |
| `J` / `K` | Next / previous call |
| `T`, `?` | Light or dark; all shortcuts |

Rebuild a report (after upgrading Callback, or to leave the audio out):

```bash
uv run callback report .callback/runs/<run id>              # add --open to open it
uv run callback report .callback/runs/<run id> --no-audio   # much smaller
```

`report.html#<call id>` opens a specific call.

Open `call.wav` in any audio editor (Audacity shows both channels) to hear the
exact moment something went wrong.

To see the buggy agent fail, start it on 8766 and point a scenario at
`restaurant-buggy` (edit `agent:` in a copy of the scripted scenario), then run
it: expect `FAIL`, exit code 1, and "The agent took 2.2 s to respond" lines.

### Trials, confidence ranges and baselines

A scenario runs `trials` times (or `--trials N`). Its limits apply to numbers across
all its calls, each with a 95% range: rates (task success, calls passed) use a Wilson
interval, and latencies pool every answered turn and use a seeded bootstrap that
resamples whole calls. So `task_success_rate: 0.8` lets one call in five miss its task.
A call that drops, runs out of time, or fails a check that has no number (the agent
never checked in on a silent caller) still fails the scenario.

Save a run as a baseline, then compare later runs with it:

```bash
uv run callback run scenarios/restaurant/move-booking-scripted.yaml --trials 3
uv run callback baseline save main                   # the latest run; --run ID for another
uv run callback run scenarios/restaurant/move-booking-scripted.yaml --trials 3 --baseline main
```

A number counts as a regression only when it got worse, its 95% range no longer
overlaps the baseline's, and it moved by at least a minimum effect (0.1 s for
latencies and time to yield by default; set others with `min_effect:` in
`callback.yaml`). A regression exits 1 even when every limit still passes.

To see one, start a slower copy of the good agent and run against it:

```bash
uv run callback agent serve --add-latency 0.4 --port 8767
```

and run the same scenario with `--agent restaurant-slow --baseline main` (the
`restaurant-slow` target in `callback.yaml` points at port 8767). The summary marks the regressed lines
`REGRESSED`, and `results.json` lists every comparison under `baseline_diff`.

Each run folder also has `junit.xml` for CI test reporters: one test suite per
scenario, a test case per call, per limit and per baseline comparison. A call that
failed inside a scenario that still passes is reported in its `system-out`, not as a
failure.

`concurrency:` in `callback.yaml` (default 1) runs that many calls at once. Calls on
the same machine compete for CPU, so latency numbers are most comparable at 1.

## 4. Chaos: break the call on purpose

Four ready-made chaos scenarios live in `scenarios/chaos/` (scripted callers, no
LLM needed):

| Scenario | What it does | Caught by |
|---|---|---|
| `barge-in.yaml` | Caller cuts in 0.3 s into the agent's 2nd turn | `time_to_yield_p95_s` (limit 0.6 s) |
| `backchannel.yaml` | "mm-hmm" / "okay" 2 s into every agent turn | `false_yields` (limit 0) |
| `silent-caller.yaml` | Caller goes quiet for 12 s instead of answering | `silence_reprompt_s` (limit 8 s) |
| `rough-line.yaml` | Street noise at 15 dB SNR, 3% packet loss, 60 ms jitter | the call still completes |

Start both agents (two terminals), then run the suite against each:

```bash
uv run callback agent serve -v                       # good, 8765
uv run callback agent serve --buggy -v --port 8766   # buggy, 8766

uv run callback run scenarios/chaos                            # good: PASS, exit 0
uv run callback run scenarios/chaos --agent restaurant-buggy   # buggy: FAIL, exit 1
```

`--agent` runs every scenario against another target from `callback.yaml`, which
is how you compare two agent configs on the same suite.

What you should see for the buggy agent, each with a one-line reason:
"kept talking for 1.x s" (barge-in), "stopped talking 0.1 s after the caller said
mm-hmm" (backchannel), "went quiet for 12.8 s and the agent never checked in"
(silence), and slow responses everywhere.

Listen to it: open `calls/<call_id>/call.wav` from the run folder. In the
barge-in call you can hear the buggy agent talk over "Sorry, it's for Saturday
evening". `events.jsonl` has every chaos action with its intended and actual
time (`intended_s` vs `t_s`).

All chaos is seeded. Every chaos type and its options are listed in
`src/callback_voice/chaos/params/`; built-in noise beds are street, cafe,
office, wind and hum (or a path to your own audio file).

### Replay one call exactly

```bash
uv run callback replay backchannel--t1          # call id from results.json / the run output
```

It re-runs that call with the same seed, the same recorded caller and the same
chaos decisions, then prints whether caller lines and chaos actions were
identical. Exit 0 means it reproduced.

## 5. Did the agent do the job? (end state, entities, judge)

`scenarios/restaurant/move-booking-scripted.yaml` checks three things after the call:
the real booking (via the agent's `/verify` webhook), that the agent read the code
`DX7Q2` back correctly, and a `must_not` rule. With both agents running:

```bash
uv run callback run scenarios/restaurant/move-booking-scripted.yaml                            # PASS
uv run callback run scenarios/restaurant/move-booking-scripted.yaml --agent restaurant-buggy   # FAIL
```

The buggy run prints `entity_fidelity 0 < 1: The agent said “B X 7 Q 2” instead of
“D X 7 Q 2”.` In `results.json`: `verifier_results` (what `/verify` returned),
`call.transcript` (both sides as text), and the judge's `experience_*` scores
(`"method": "judge"`, never pass/fail) with the judge's model and prompt version under
`judge`. The first run downloads the `small` Whisper model (~460 MB) used for
transcribing the agent after the call.

To see a task failure: copy the scenario and set `match: {hour: 20}`; the run fails
with "hour is 19, expected 20".

The judge is optional. To turn it on, uncomment `judge:` under `providers:` in
`callback.yaml` (Gemini free tier, needs `GEMINI_API_KEY`). Its scores never fail a run.

### Task bugs, more facts, and the review list

`scenarios/restaurant/move-and-resize.yaml` moves the booking, changes the party size,
and checks the booking code, party size, time and phone number the agent reads back,
plus a rule against revealing other guests' bookings. `callback.yaml` has one target
per buggy task bug:

```bash
uv run callback run scenarios/restaurant/move-and-resize.yaml                                              # PASS
uv run callback run scenarios/restaurant/move-and-resize.yaml --agent restaurant-buggy-wrong-hour           # hour is 20, expected 19
uv run callback run scenarios/restaurant/move-and-resize.yaml --agent restaurant-buggy-ignores-party-change # party_size is 4, expected 5
uv run callback run scenarios/restaurant/move-and-resize.yaml --agent restaurant-buggy-confirms-without-saving
```

With plain `restaurant-buggy`, one task bug is picked per call from the call id (the
agent log says which: `task bug: wrong_hour`).

When Callback can't tell whether the agent said a fact wrong or the line swallowed a
sound, the fact goes under `review` in `results.json` and prints as
"▲ 1 check(s) need a person to listen", without failing the run.

## 6. Recorded mode (zero LLM cost)

The first run of an LLM scenario records the caller's lines to
`.callback/cache/cassettes/`. Later runs replay them without calling Gemini.

```bash
uv run callback run scenarios/restaurant/move-booking-persona.yaml --record   # fresh LLM caller
uv run callback run scenarios/restaurant/move-booking-persona.yaml --replay   # no LLM at all
```

Editing the scenario's `caller:` block invalidates its recording automatically.
If the agent's behaviour changes enough that the recorded caller no longer fits,
the run errors (exit 2) and tells you to `--record` again.

## 7. The automated test suite

Callback's tests are end-to-end only: they drive the real CLI, start the real
reference agent as a separate process, place real calls with real speech models,
and check real outputs.

```bash
uv run pytest                                  # everything (~20 min, real calls)
uv run pytest tests/e2e/test_cli.py            # CLI contract only (seconds)
uv run pytest tests/e2e/test_scoring_accuracy.py   # scorer timing accuracy (seconds)
uv run pytest -k llm                           # the Gemini caller test
uv run pytest -x -v                            # stop at first failure, verbose
```

| Test file | What it proves |
|---|---|
| `test_cli.py` | Commands, error messages and exit codes; a full example scenario with every chaos type validates |
| `test_scoring_accuracy.py` | Synthetic calls with known timings score within ±50 ms |
| `test_reference_agent_calls.py` | A scripted call completes, the booking really moves, good agent passes latency, buggy agent fails it |
| `test_cli_run.py` | `callback run` end to end: results files, error exit 2, the Gemini caller reaches its goal, replay works with no API key |
| `test_chaos.py` | The good agent passes every chaos scenario; the buggy agent is caught by barge-in, backchannel and silence; `callback replay` reproduces a call |
| `test_verifiers.py` | End state via the webhook (pass, and a wrong expectation that fails with the exact difference), the buggy agent's garbled code is named, an unreachable webhook exits 2, judge scores are informational |
| `test_task_bugs.py` | Each buggy task bug is caught by the end state on a real call; the good agent passes four facts; the leak rule fires |
| `test_fact_checks.py` | A noise-masked letter goes to review; a spoken wrong letter fails; counts, times and phones are matched |
| `test_disagreement_fixture.py` | The saved judge-vs-facts call still fails the hard check |
| `test_report.py` | The report is one self-contained file; its timings match a fixture call's known latencies; 63-bit seeds survive; the summary sentence and tiles for a failing, a passing and an older run; `--no-audio` and a missing run |
| `test_baseline_gate.py` | Three calls saved as a baseline; the same agent again exits 0; the agent with 0.4 s added exits 1 on the baseline alone, with the regression in `junit.xml` |

Tests that need local models skip themselves when `[local]` isn't installed; the
Gemini test skips when `GEMINI_API_KEY` isn't set.

On GitHub, the `ci` workflow runs on every push and pull request. It installs
without `[local]` and with no keys, so only the fast tests run (CLI contract and
scoring on the committed fixture calls; the tests take seconds). The full suite with real
calls is the `e2e` workflow, started by hand from the Actions tab (Run workflow).
To run the same fast set locally, use a separate environment without `[local]`:

```bash
UV_PROJECT_ENVIRONMENT=.venv-fast uv sync --locked
UV_PROJECT_ENVIRONMENT=.venv-fast uv run pytest -rs
```

Rebuild the synthetic scoring fixtures (only after changing them):

```bash
uv run python tests/fixtures/build_fixtures.py
```

## 8. Lint and types

```bash
uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Kokoro needs espeak-ng` | `brew install espeak-ng` |
| `cannot connect to ws://127.0.0.1:8765` (exit 2) | The agent isn't running: `uv run callback agent serve` |
| `$GEMINI_API_KEY is not set` | Add it to `.env` at the repo root |
| First call is slow | Models are loading/downloading once; later runs are fast |
| `the recorded caller ran out of lines` | The agent changed; re-run with `--record` |
