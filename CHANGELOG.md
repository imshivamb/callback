# Changelog

## 0.1.2 (2026-10-03)

### Added

- **`agent_name` on LiveKit targets.** A LiveKit Agents worker registered with an
  `agent_name` only joins rooms it is explicitly sent to, so Callback waited 20 s for an
  agent that never came. Set `agent_name` and Callback asks for that agent in every room
  it creates. See [docs/transports.md](docs/transports.md).
- **Folded interruptions.** When a caller cuts in and the agent does not answer on its
  own but works the point into its next full reply, the turn no longer counts in
  `unanswered_turns`. It is reported in a new `folded_turns` metric and as a warning on
  the timeline. The match is a word-overlap check on the recognised speech: a content
  word the interruption introduced must appear in the agent's next reply. A late,
  cut-off acknowledgement over the caller's next line is not that reply.

### Changed

- **A redesigned report.** The report now leads with the verdict in plain words, then
  *What went wrong*: each problem with its number and limit, a small picture of the moment
  it happened and a **Hear it** button. *Every call* shows all calls as aligned tapes,
  grouped by scenario, so a pattern shows at a glance. The call player and the numbers
  (now a dot, a 95% range and a limit on one line) keep everything they had: timeline,
  zoom, shortcuts, audio, baseline comparison. It opens on the call with the worst
  problem, and is still one file that opens offline (it embeds a 22 KB subset of the
  Bricolage Grotesque typeface, SIL OFL).
- **One clause per kind of problem.** When many scenarios had the same problem with
  different numbers, the summary sentence repeated it once per scenario ("replies too
  slowly (3.69 s…), replies too slowly (3.62 s…)"). It now says it once, with the worst
  case, and the report lists up to five kinds instead of three.

### Fixed

- **The report's speech view no longer shows the caller's words as the agent's.** For a
  call with a transcript, each agent stretch carried the text of every overlapping turn,
  the caller's included, and repeated a whole turn on each piece. Each stretch now carries
  only the agent's own words inside it. No metric changes.

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
