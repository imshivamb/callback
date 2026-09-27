# Testing Callback yourself

Everything below runs locally. The only thing that may call the internet is the
simulated caller's LLM (Gemini free tier) and one-time model downloads.

Last updated for milestone **M4** (LLM caller, `callback run`).

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

Each run folder has `results.json` and one folder per call under `calls/` with:

| File | What it is |
|---|---|
| `call.wav` | Stereo recording: **left = caller**, **right = agent**, one shared clock |
| `caller_clean.wav` | The caller's voice without chaos (noise, packet loss) |
| `events.jsonl` | Every caller line, agent turn, chaos action, with timings |

Open `call.wav` in any audio editor (Audacity shows both channels) to hear the
exact moment something went wrong.

To see the buggy agent fail, start it on 8766 and point a scenario at
`restaurant-buggy` (edit `agent:` in a copy of the scripted scenario), then run
it: expect `FAIL`, exit code 1, and "The agent took 2.2 s to respond" lines.

## 4. Recorded mode (zero LLM cost)

The first run of an LLM scenario records the caller's lines to
`.callback/cache/cassettes/`. Later runs replay them without calling Gemini.

```bash
uv run callback run scenarios/restaurant/move-booking-persona.yaml --record   # fresh LLM caller
uv run callback run scenarios/restaurant/move-booking-persona.yaml --replay   # no LLM at all
```

Editing the scenario's `caller:` block invalidates its recording automatically.
If the agent's behaviour changes enough that the recorded caller no longer fits,
the run errors (exit 2) and tells you to `--record` again.

## 5. The automated test suite

Callback's tests are end-to-end only: they drive the real CLI, start the real
reference agent as a separate process, place real calls with real speech models,
and check real outputs.

```bash
uv run pytest                                  # everything (~8 min)
uv run pytest tests/e2e/test_cli.py            # CLI contract only (seconds)
uv run pytest tests/e2e/test_scoring_accuracy.py   # scorer timing accuracy (seconds)
uv run pytest -k llm                           # the Gemini caller test
uv run pytest -x -v                            # stop at first failure, verbose
```

| Test file | What it proves |
|---|---|
| `test_cli.py` | Commands, error messages and exit codes; the spec's example scenario validates |
| `test_scoring_accuracy.py` | Synthetic calls with known timings score within ±50 ms |
| `test_reference_agent_calls.py` | A scripted call completes, the booking really moves, good agent passes latency, buggy agent fails it |
| `test_cli_run.py` | `callback run` end to end: results files, error exit 2, the Gemini caller reaches its goal, replay works with no API key |

Tests that need local models skip themselves when `[local]` isn't installed; the
Gemini test skips when `GEMINI_API_KEY` isn't set.

Rebuild the synthetic scoring fixtures (only after changing them):

```bash
uv run python tests/fixtures/build_fixtures.py
```

## 6. Lint and types

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
