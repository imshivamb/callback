# Verification run after fixes, 2026-09-30

18 calls against the bundled reference agents, the same way as the
[baseline](../before-2026-09-30), after the fixes listed under 0.1.1 in the
[changelog](../../../CHANGELOG.md): the scripted, noisy and AI-caller booking
scenarios, good and buggy agent, 3 calls each. The AI caller was recorded fresh.

Run it yourself: start both agents (see [`../callback.yaml`](../callback.yaml)), then
in this folder `callback run scenarios --record`.

`after-2026-09-30/`:

- `results.json`, `junit.xml`: run `20260930-153311`.
- `cassettes/`: the AI caller's recorded lines, with each line's timing.
- `replays/`: `callback replay` of the good agent's three AI-caller calls
  (`20260930-160117`, `-160258`, `-160409`).
- `checks/`: one buggy-agent barge-in call (`20260930-160721`).

Setup: Callback 0.1.1 at commit `1231256`, one call at a time, caller model
`gemini-3.5-flash-lite`, on one Mac (Apple Silicon, on AC power), reference agents
with a warm phrase cache. The recordings are not included.
