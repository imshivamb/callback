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

## 2b. The demo and a new project

```bash
uv run callback demo            # buggy agent, two chaos calls, report opens; exit 1
uv run callback demo --good     # the good agent; exit 0
uv run callback demo --no-open  # don't open the browser (CI)
```

The demo starts the reference agent in its own process on a free port, runs the
bundled barge-in and backchannel scenarios (scripted callers, no LLM, no keys),
writes the usual run folder under `.callback/runs/` in the current folder, and stops
the agent. Without the local speech extra or espeak-ng it exits 2 and prints the
install command.

`uv run callback init` in an empty folder writes `callback.yaml` (a `my-agent`
target on port 8765) and `scenarios/example.yaml` (one scripted call with a barge-in).
With `callback agent serve` running, `callback run scenarios` passes. It refuses to
overwrite existing files unless you pass `--force`.

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

1. **What ran, in plain words**, e.g. "24 calls ran. 5 of 6 checks went above target at
   least once", with the exit code and a note that the limits are the ones set in each
   scenario. It describes what was measured; it does not grade the agent.
2. **Check by check**: for each limit, how many of the calls it applied to stayed within
   it, next to what was measured. What held sits beside what did not.
3. **What stood out**: the behaviours that went above target, most serious first, one row per
   kind across all the calls. Each row says how many times it happened and in how many calls,
   lists those calls by number (select one to open it), names the worst case, shows a typical
   moment as a small picture (caller above, agent below, the stretch above target hatched in
   amber) with the number that goes with it, and has **Hear a typical one**. A sentence above
   the rows says how the calls differ: for example that slow replies are in all 24 calls and
   seven calls also had something else.
4. **Every call**: one row per call, numbered, grouped by scenario and drawn on the same
   clock, so a pattern (the agent always answering late, say) shows at a glance. Under each
   row is what went above target in that call. Amber ticks are targets passed; magenta ◆
   marks disturbances Callback caused. Select a call to open it; the call picker above the
   player moves between calls.
5. **The call**: caller and agent waveforms on one time axis, an Events row, a "Wait
   before reply" bar per answer against the dashed limit, and a whole-call strip to move
   around. It opens on the call with the worst problem. Below it, the problems in that
   call; repeats are grouped ("Slow reply ×6") with a chip per occurrence.
6. **The numbers** (folded, one section per scenario): every number across calls as a dot
   on a line, with its 95% range as a whisker and its limit as a dashed line. The ⓘ next
   to a term explains it on hover or keyboard focus.

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

`same_turn_pause_s:` in `callback.yaml` (default 0.5) decides, after the caller has
spoken over the agent, whether the agent speaking again is an answer or just the next
sentence: a pause shorter than this is the same turn. Raise it for agents with long
pauses between sentences.

`concurrency:` in `callback.yaml` (default 1) runs that many calls at once. Results
stay in plan order with the same seeds, but calls on one machine compete for CPU and
latency goes up: three scripted calls to the good agent measured a reply-delay p95 of
0.91 s one at a time and 1.23 s three at a time (per call 0.90, 1.12, 1.31 s), in 100 s
instead of 249 s. Each run records its concurrency, and `--baseline` warns when the
baseline was made at a different one. Keep baseline runs at the same concurrency,
ideally 1.

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

Every call is also checked for **unanswered turns** (`unanswered_turns`, limit 0): the
caller finished, waited at least the reply-delay limit (1.5 s by default) in silence,
and the agent said nothing. A caller who goes straight on to the next sentence gave the
agent no opening, so that does not count. A turn the agent talked over to the end is
judged from when the agent stopped talking. `tests/fixtures/calls/unanswered/` holds a
synthetic call with one real unanswered turn and one back-to-back pair that must not
count.

To see one on a real call, run the buggy agent with interruptions ignored completely
(`?barge_in=ignore` on its URL; the `restaurant-buggy-ignores-interruptions` target in
`callback.yaml`):

```bash
uv run callback agent serve --buggy --port 8766
uv run callback run scenarios/restaurant/ignored-interruption.yaml   # FAIL, exit 1
```

The agent talks straight over "Sorry, it's for Saturday evening." and never answers it.
The caller waits 2.5 s for a reply (noted in the event log as "no reply to the
interruption; caller goes on"), then carries on. The report's
worst problem is "Left the caller unanswered".

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

#### Writing `must_not` rules

A `must_not` entry is either a pattern (`{says: <regular expression>, why: ...}`),
checked on every call, or a plain-English sentence, which only the judge can check.

- **Match what speech recognition writes, not what the agent meant.** Patterns run
  on a transcript of the agent's audio, and names get spelled freely: in my test
  runs the agent said "Okafor" and the transcript said "Akafer" every time, so a rule
  listing guest names missed every leak. Match the shape of the sentence instead, as
  the bundled scenarios do: `\bthe \w+ party (already )?(has|is booked)`.
- **Plain-English rules need the judge.** Without one they are not checked, and
  Callback says so: a warning before the first call, `rules_not_checked` on each
  call, and a note at the top of the report. They are never counted as passed.

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

Each recorded line also keeps how long the live caller took to decide it and to be
ready to speak it (a second or two, mostly the LLM). A replay takes the same time,
so the agent hears the caller at the same moments; a caller that answered instantly
would cut into the agent's pauses and change the call. Recordings made by Callback
0.1.0 have no timing: they still replay, but the call's event log says so and the
call can differ from the original. Re-record them with `--record`.

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
| `test_demo.py` | `callback demo` exits 1 with the buggy agent's barge-in and backchannel failures and writes a report; without the local extra it prints the install command |
| `test_concurrency.py` | Three calls at once keep plan order and seeds and record the concurrency; a baseline made at another concurrency is flagged |
| `test_baseline_gate.py` | Three calls saved as a baseline; the same agent again exits 0; the agent with 0.4 s added exits 1 on the baseline alone, with the regression in `junit.xml` |

Tests that need local models skip themselves when `[local]` isn't installed; the
Gemini test skips when `GEMINI_API_KEY` isn't set.

### The CI latency limit

The full suite (`e2e` workflow) runs on GitHub's shared runners, which synthesise
speech 2–3× slower than a laptop. There the good reference agent's reply-delay p95 was
0.95–1.70 s on Ubuntu and up to 3.56 s on macOS, against the real 1.5 s target. So the
workflow sets `CALLBACK_CI_LATENCY_LIMIT_S=2.0`:

- It only loosens the reply-delay limit (a scenario's own limit wins if it is higher),
  and only when that variable is set. Nothing sets it by default.
- It is not the target. Every run that uses it records it in `results.json` under
  `limit_overrides` (with the real target next to it), prints it before the first call,
  and shows a banner at the top of the report.
- 2.0 s was chosen from measured runs: on Ubuntu the good agent stayed at or below
  1.70 s and the buggy agent at or above 2.25 s, so the check still fails the buggy
  agent.
- On macOS runners no limit separates the two agents (good up to 3.56 s, buggy from
  2.43 s).
- The whole `e2e` workflow is informational on GitHub, on both OSes: shared runners are
  too slow and noisy for the real-call suite to pass reliably, even with these limits.
  Every run keeps its results, reports and agent logs as artifacts, but a failure
  doesn't turn the workflow red. The required gate is the fast `ci` workflow, and the
  full suite (`uv run pytest`) is run locally before a release.

The workflow also sets `CALLBACK_CI_DRIFT_LIMIT_S=1.0`, the tolerance for how late
Callback's own disturbances may land (normally 0.1 s). This is a check on Callback, not
on the agent, and never fails a run; on busy runners the worst call drifted 0.86 s
(Ubuntu) and 1.63 s (macOS), against 4 ms on a laptop, so chaos timing on CI is less
precise than locally. Each call's drift is shown in its report header.

Every other check (interruptions, "mm-hmm", silence, end state, facts, replay) is as
strict on CI as anywhere. `CALLBACK_CI_YIELD_LIMIT_S` works like the latency limit for
the time to stop when interrupted; the example workflow for your own CI sets it to
1.1 s ([why](ci-example.md#absolute-limits-on-slow-runners)), but the `e2e` workflow
does not, so there the good agent's 0.59–0.64 s against 0.6 s can fail. The unanswered-turn check has its own threshold
(`unanswered_wait_s`, 1.5 s: how long the caller must wait in silence), which the CI
latency limit does not touch.

On GitHub, the `ci` workflow runs on every push and pull request. It installs
without `[local]` and with no keys, so only the fast tests run (CLI contract and
scoring on the committed fixture calls; the tests take seconds). The full suite with real
calls is the `e2e` workflow, started by hand from the Actions tab (Run workflow); it is
informational (see "The CI latency limit" above). The `clean-install` workflow installs
the built wheel with plain pip on fresh Ubuntu and macOS machines and runs
`callback demo`, expecting exit code 1 and a report; it runs by hand and on every
published release.
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
