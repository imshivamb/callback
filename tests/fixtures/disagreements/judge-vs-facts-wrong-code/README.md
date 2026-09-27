# Fixture: judge vs facts, wrong booking code

A real call (run `20260927-103325`, `move-booking-persona--t1`) between the Gemini
persona caller and the **buggy** reference agent, whose code read-back garbles "D" as
"B".

What happened in the call:

- 21.8 s, caller: "It is D X 7 Q 2."
- 26.0–35.3 s, agent: "... reference **B, X, 7, Q, 2** ..." (the bug)
- 40.3 s, caller, noticing: "Actually it is D X 7 Q 2, ..."

How it was scored at the time (`recorded.json`):

| Check | Kind | Verdict |
|---|---|---|
| `entity_fidelity` (DX7Q2) | deterministic | **fail**: "The agent said “B X 7 Q 2” instead of “D X 7 Q 2”." |
| `task_success` | deterministic | pass (the booking itself moved correctly) |
| LLM judge (`gemini-flash-lite-latest`, `judge-v1`) | judge | concise 4, no repetition 5, handles frustration 5: "handling a minor transcription error smoothly" |

Why it is kept: it is the clearest example of why only deterministic checks can fail
a run. The judge read the wrong code in the transcript and excused it.

Files: `call.mp3` (full call, left channel caller, right channel agent),
`events.jsonl` (the call's event log), `recorded.json` (judge output, hard checks,
transcript as recorded), `expected.json` (what re-scoring must find).
`tests/e2e/test_disagreement_fixture.py` re-scores it and requires the hard check to
still call the code wrong, not uncertain.
