# Baseline run, 2026-09-30

The 100-call run in [`../scenarios`](../scenarios) as it was before a set of fixes to
Callback, kept to compare against the run after them.

- `results.json`: every metric of every call (run `20260930-032808`).
- `junit.xml`: pass/fail per call.
- `cassettes/`: the AI caller's recorded lines for the 20 AI-caller calls.

Setup: Callback 0.1.0 at commit `fb1aae0`, one call at a time, caller model
`gemini-3.5-flash-lite`, on one Mac (Apple Silicon, on AC power), reference agents
with a warm phrase cache. The recordings (808 MB) are not included.
