# Results: Callback against its reference agents

These runs test **Callback itself**. It called two agents I wrote, a good one and a
copy with deliberately planted bugs, to check that it catches every planted bug and
never fails the good agent. They say nothing about voice agents in general.

A 100-call run with Callback 0.1.0 found five problems in Callback. After fixing
them in 0.1.1, an 18-call run checked the fixes.

## What was tested

| | Before | After |
|---|---|---|
| Callback | 0.1.0 (commit `fb1aae0`) | 0.1.1 (commit `1231256`) |
| Calls | **100**: 17 scenario/agent pairs; 80 scripted callers, 20 AI callers | **18**: 3 booking scenarios × 2 agents × 3 calls; 12 scripted, 6 AI callers |
| Scenarios | barge-in, backchannel, rough line, silent caller, ignored interruption, 4 booking tasks | the 3 booking tasks that had problems: scripted, noisy line, AI caller |
| Extra checks | 3 replays | 3 replays, 1 barge-in call |
| Files | [`reference-agents/before-2026-09-30/`](reference-agents/before-2026-09-30) | [`reference-agents/verification/after-2026-09-30/`](reference-agents/verification/after-2026-09-30) |

Same setup for both: one Mac (Apple Silicon, on AC power), one call at a time,
local speech models, AI caller `gemini-3.5-flash-lite`.

The agents ([`reference-agents/scenarios/`](reference-agents/scenarios)):

- **good**: answers promptly, stops when interrupted, talks through "mm-hmm",
  checks in on a silent caller.
- **buggy**, with planted bugs:
  - slow replies;
  - microphone muted for the first 1.8 s of each reply;
  - stops for any sound;
  - never checks in on a silent caller;
  - reads the booking code wrong;
  - reveals another guest's booking;
  - one task bug per call (wrong hour saved, party-size change ignored, or
    confirmed without saving).
- **buggy, ignoring interruptions**: the buggy agent with interruptions ignored
  completely.

## Before: 100 calls

The run was clean: 0 calls errored, all 100 ended with the caller hanging up, and
Callback's own timing never fell behind by more than 0.1 s. **45 of 100 calls
passed: exactly the 45 good-agent calls.** All 55 buggy calls failed.

| Measure | Good agent | Buggy agent |
|---|---|---|
| Reply delay p95, per call | 0.62–0.745 s (45 calls) | 1.93–2.44 s (45 calls) |
| Time to stop when interrupted | 0.49–0.53 s (5 calls) | 1.87–1.89 s (5); ignoring agent 5.34–5.38 s (10) |
| Stops for "mm-hmm" | 0 per call (5 calls) | 6 per call (5 calls) |
| Checks in on a silent caller | after 5.08–5.10 s (5 calls) | never (5 of 5 caught) |
| Reads the booking code back correctly | 25 of 25 calls | 0 of 25 calls |

The good and buggy ranges don't overlap on any of these measures. With 0 false
failures in 45 good-agent calls, the false-failure rate for this setup is below
about 7% (95% confidence).

### What it found in Callback

| Problem | Evidence (before) |
|---|---|
| **Leak rules that list names missed every leak.** Speech recognition wrote the agent's "Okafor" as "Akafer". | The leak sentence is in the transcript of all 25 buggy booking calls. Flagged in 5 (the rule matching the sentence's shape), 0 of 10 (rules listing guest names), and 10 had no leak rule. |
| **Plain-English rules were skipped without a judge and looked like a pass.** | 20 calls had such a rule and no judge; none recorded it as unchecked (only a detail, "1 rule(s) checked", hinted at it). |
| **Replaying an AI-caller call was not exact.** The replayed caller spoke without the live caller's thinking time and cut into the agent. | 1 AI-caller replay: failed where the original passed, with caller lines up to 17 s off. 2 scripted replays: same lines within 0.04 s, same verdicts. |
| **Actual LLM use was never recorded**, only an estimate before the run. | No usage in `results.json`; the 20 AI-caller calls produced 125 caller lines. |
| **"Says one time, saves another" is not caught with AI callers.** | 3 AI-caller calls confirmed 7:30 PM on the call and saved 8:30 PM; all passed the task check. Not fixed: see [Known limitation](#known-limitation). |

## After: 18 calls with the fixes

**9 of 18 calls passed: exactly the 9 good-agent calls.** 0 errors.

| Problem | Before | After |
|---|---|---|
| Leak flagged in buggy calls where it happened | 5 of 25 | **9 of 9** |
| Leak flagged in good-agent calls (false alarms) | 0 of 25 | 0 of 9 |
| Plain-English rules without a judge | 20 of 20 calls silently skipped | **12 of 12** recorded as "not checked"; a warning before the run and a note in the report |
| AI-caller replays matching the original | 0 of 1 | **2 of 3** (see [Replay](#replay-of-ai-caller-calls)) |
| LLM use recorded | no | **yes**: 36 requests, 20,139 input + 1,098 output tokens, $0.05 at Google's paid price ($0 on the free tier) |
| Buggy agent reply delay p95, per call | 1.93–2.44 s (45) | 1.95–2.18 s (9) |
| Good agent reply delay p95, per call | 0.62–0.745 s (45) | 0.64–0.76 s (9) |

**About the sample size.** "After" is 18 calls, 3 per scenario/agent pair. It shows
that the fixes work on these calls; it can't show how often they fail on others.

- 9 of 9 leaks flagged is consistent with a true catch rate as low as about 72%
  (95% confidence).
- 0 false alarms in 9 good-agent calls is consistent with a false-alarm rate up to
  about 28%.
- The reply-delay rows are there to show nothing else changed. They are not a
  comparison: the runs cover different scenarios and sample sizes.

### Replay of AI-caller calls

A replayed AI caller now waits as long as the live caller did before each line.
Of 3 replays:

- **2 matched the original:** same lines, starting within 0.04 s, same verdict.
- **1 diverged.** The caller's lines started at the recorded moments, but after
  "It is D X 7 Q 2" the agent under test asked for the booking code again, which it
  had not done in the original call. A live AI caller would have repeated the code;
  a replayed caller can only say its recorded lines, so the call failed.

This is the agent answering differently to the same audio, which replay can't
prevent. Callback does not yet say which side diverged; it only reports that
the caller's lines differ.

## Caveats

- **My own agents.** I wrote both agents and every bug. These results
  say how reliably Callback catches known bugs in these agents, not how real voice
  agents behave.
- **One machine.** All reply delays are from one Mac. Shared CI runners and
  smaller machines are slower (see [docs/ci-example.md](../docs/ci-example.md)).
- **Warm cache.** The reference agents cache every sentence they synthesise, and the
  cache was warm, so these are warm-agent numbers. First calls on a fresh machine
  are slower.
- **Small "after" run.** See the sample-size note above.
- **Replay** is exact on Callback's side only; see above.
- **Before, LLM use is unmeasured.** Only the "after" run records it.
- **Recordings are not included** (808 MB for the 100-call run). Each folder has the
  results, JUnit and the AI caller's recorded lines.

## Known limitation

**"Says one time, saves another" with AI callers.** An AI caller chooses the time
during the call, so its scenario can only accept a range (7–9 PM). An agent that
confirms 7:30 PM and saves 8:30 PM passes. It happened in 3 of 3 buggy AI-caller
calls in each run. A check that compares what the agent confirmed on the call
with what it saved is planned for 0.2 ([CHANGELOG](../CHANGELOG.md)).

## Reproduce

Start both agents, then run each folder's scenarios:

```bash
callback agent serve                        # good agent, port 8765 (terminal 1)
callback agent serve --buggy --port 8766    # buggy agent, port 8766 (terminal 2)
```

Then, from the repository root:

```bash
cd results/reference-agents && callback run scenarios                   # before: 100 calls, ~2.5 h
cd results/reference-agents/verification && callback run scenarios --record   # after: 18 calls, ~30 min
```

AI-caller calls need `GEMINI_API_KEY`. The scenario files now carry the fixed leak
rules; to repeat the "before" run exactly, check out commit `fb1aae0` first. Every
number above comes from the `results.json` files in these folders.
