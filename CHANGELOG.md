# Changelog

## 0.1.1 (2026-09-30)

Fixes for problems found by a 100-call run against the bundled reference agents
([results](results/README.md)).

### Fixed

- **Plain-English `must_not` rules without a judge are reported as not checked.**
  They need the LLM judge; without one they were dropped and the call's policy
  check read as a pass. Now each call records `rules_not_checked`, `callback run`
  warns before the first call, and the report says so at the top.
- **Replayed AI callers keep their live timing.** Recordings kept only the caller's
  words, so on replay the caller answered instantly, cut into the agent's pauses
  and could change the call. Recordings now keep each line's timing (format
  version 2) and replay waits the same. Recordings made with 0.1.0 still replay,
  with a note in the call's event log; re-record them with `--record`.
- **Leak rules in the bundled scenarios match the sentence, not guest names.**
  Speech recognition spelled the guest name differently, so rules listing names
  missed every leak. The AI-caller scenario also gets a leak rule. See "Writing
  `must_not` rules" in [docs/testing.md](docs/testing.md).
- **Actual LLM use is recorded.** `results.json` records the caller's and judge's
  requests, tokens and cost per call and in total, and `callback run` prints them;
  before, only the estimate before the run existed.
- The buggy reference agent no longer logs one stop decision many times.

### Known limitations (planned for 0.2)

- **"Says one thing, saves another" is not caught with AI callers.** When the caller
  improvises, the scenario cannot know in advance which time it will pick, so the
  end-state check accepts a range; an agent that confirms 7:30 PM on the call and
  saves 8:30 PM passes it. A check comparing what the agent confirmed on the call
  with what it saved is planned.

## 0.1.0 (2026-09-29)

First release: `callback run`, `demo`, `init`, `doctor`, `replay` and `baseline`;
WebSocket and LiveKit transports; chaos scenarios; HTML, JSON and JUnit reports.
