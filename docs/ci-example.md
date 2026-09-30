# Running Callback in your CI

[`examples/callback-ci.yml`](examples/callback-ci.yml) is a GitHub Actions workflow
that calls your voice agent on every pull request, fails when a number got really
worse against a saved baseline, and keeps the report. Copy it to
`.github/workflows/callback.yml` in your agent's repository and edit the marked lines.

I tested it in a public repository with the bundled reference agent, a 3-call
scenario and the baseline recorded on the same runner: the unchanged agent passed
(reply-delay p95 0.99 s against a baseline of 1.01 s, nothing regressed), and the same
agent made 0.4 s slower failed the job (1.38 s, +0.37 s regressed) while every call
still passed its own limits. That test was not of the file exactly as shipped: the
agent stopped 0.65–1.05 s after being interrupted on those runners, against the
scenario's 0.6 s limit, so the time-to-yield limit was loosened in the test copy's
scenario. The shipped file now does that with `CALLBACK_CI_YIELD_LIMIT_S` instead
([below](#absolute-limits-on-slow-runners)); this version has not been re-run in that
repository.

## What to commit first

By default Callback keeps everything under `.callback/`, which you should not commit
(recordings add up). Two things CI needs do belong in git, so point them elsewhere in
`callback.yaml`:

```yaml
cache_dir: callback-cache       # recorded AI-caller lines, replayed in CI
baseline_dir: callback-baselines  # the saved baseline(s) CI compares against
```

Then, on a machine that can reach your agent:

```bash
callback run scenarios --record        # records AI callers' lines (needs the LLM key once)
callback run scenarios                 # the run you want as the reference
callback baseline save main
git add callback.yaml scenarios callback-cache callback-baselines
```

Scripted callers need no recording; only AI (persona) callers do. A recording keeps
each line's timing as well as its words, so CI replays the caller at the pace it
had live. Recordings made with Callback 0.1.0 have no timing; re-record them with
`--record` after upgrading.

## What the workflow does

1. Installs Callback with its local speech models and espeak-ng, and caches the model
   downloads (a few hundred MB, once).
2. Starts your agent (**edit this step**), waits until it answers, and makes one
   throwaway call: the first call after an agent starts is slower, and it would widen
   the numbers enough to hide a real regression.
3. `callback run scenarios --replay --baseline main`: replays the recorded callers
   (no LLM calls, no API key), and compares every number with the baseline. Exit code
   0 passes, 1 means a limit failed or something regressed, 2 means the run could not
   happen (an error is never reported as a pass).
4. Uploads `report.html`, `results.json` and `junit.xml` from the run, pass or fail.

## Record the baseline on the same kind of machine

Reply delay depends on the machine. GitHub's shared runners synthesise speech 2–3×
slower than a laptop, and parallel calls on one machine are slower again. A baseline
recorded on your laptop and compared on a runner will look like a regression that
isn't one (a run at a different concurrency prints a warning). Record the baseline on
the same runner type you compare on: run the workflow by hand (Actions → callback →
Run workflow) with **save_baseline** ticked, download the `callback-baseline` artifact,
and commit `callback-baselines/main.json`.

A regression is flagged only when a number got worse, its 95% range no longer
overlaps the baseline's, and it moved by at least the minimum effect (0.1 s for
latencies by default; `min_effect:` in `callback.yaml`).

**Private repositories get smaller runners.** GitHub's standard `ubuntu-latest`
runner has 4 CPU cores for public repositories and 2 for private ones. Your agent,
Callback's caller and the scoring share those cores. In my test the same example was
about 3× slower in a private repository (reply-delay p95 4.1 s) than in a public one
(0.97 s per call after the first). Record the baseline in the repository, and on the
runner type, where you compare.

## How many trials on a noisy runner

Each scenario's `trials` is how many calls the numbers are based on. The quieter the
machine, the fewer you need:

- **Quiet runner** (my public Ubuntu runner: the same agent's calls within 0.03 s of
  each other): 3 trials caught an added 0.4 s delay every time, in the real test and in
  a simulation built from those calls, with no false alarms.
- **Noisy runner** (GitHub's macOS runners: the same agent's calls ranged from 1.0 to
  2.1 s at p95, and a whole run could be 0.27 s slower than the previous one). Here
  the p95 check caught an added 0.4 s delay only 28% of the time with 3 trials and 50%
  with 20; the median (p50) check was much steadier, catching it in 99% of simulated
  3-trial runs. The whole-run shift, which more trials cannot remove, still made a real
  run miss it.

So on a noisy runner use **at least 10 trials** per scenario you gate on, rely on the
p50 comparison (it is part of every baseline check), and expect to miss changes
smaller than about 0.5 s. For small regressions, use a quieter or dedicated runner.
These numbers come from 6–13 calls per runner, so treat them as a starting point and
measure your own runners.

## Absolute limits on slow runners

Scenario limits (for example reply delay p95 ≤ 1.5 s) are absolute. If your agent
runs on the same shared runner as Callback, it may miss them there for reasons that
have nothing to do with your change. You can loosen the reply delay and the time to
stop when interrupted for CI only:

```yaml
    env:
      CALLBACK_CI_LATENCY_LIMIT_S: "2.0"   # reply delay p95; pick from your own runs
      CALLBACK_CI_YIELD_LIMIT_S: "1.1"     # time to stop when interrupted (p95)
```

When reply delay fails on GitHub Actions, `callback run` prints the runner's CPU
core count and points at `CALLBACK_CI_LATENCY_LIMIT_S`; it never loosens anything
on its own.

Every run that uses them records the loosened limit next to the real target in
`results.json` and shows it at the top of the report, so it is never mistaken for
the target. The baseline comparison is unaffected, and so is the talk-over check,
which keeps the real time-to-yield target as its grace period.

**Why the example sets the time-to-yield allowance to 1.1 s.** The `callback init`
scenario expects the agent to stop within 0.6 s of being interrupted. The reference
agent stops in 0.49 s on a laptop, but on GitHub's runners it measured 0.59–0.64 s
(6 calls, public repository, 4 cores) and 0.94–1.05 s (private repository, 2 cores).
Its speed there is limited by the small speech model it uses to tell "sorry, wait"
from "mm-hmm", which runs 2–3× slower on busy shared CPUs; waiting less before
judging made it miss real interruptions. 1.1 s passes every call I measured, while
the deliberately buggy agent still fails clearly: its microphone is muted for the
first 1.8 s of every reply and it keeps talking 0.6 s after deciding to stop, so it
took 1.89 s to stop in my barge-in test on a laptop (both delays are counted in audio played, so
a slower machine can only make that later). An agent that ignores interruptions
fails by seconds. Your agent's numbers will differ: measure them, and on a dedicated
or larger runner remove the allowance. For latency you can trust as an
absolute number, use a dedicated or larger runner, or point Callback at a deployed
agent instead of one started inside the job.
