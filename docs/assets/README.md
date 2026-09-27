# Assets

Recordings and a figure from real test calls against the two example agents that ship
with Callback: a well-behaved restaurant booking agent ("good") and a copy with
deliberate bugs ("buggy"). Every audio clip is stereo: **left channel is the simulated
caller, right channel is the agent**. Clips are trimmed to the 12–13 seconds that
matter.

| File | What you see or hear |
|---|---|
| `false-yield-mm-hmm.png` | Caller (top) and agent (bottom) on one time axis. The caller says "mm-hmm" at 2.1 s, meaning "I'm listening, go on". The agent stops talking at 2.9 s and never finishes its greeting. This was an early version of the good agent: its quick speech check heard the "mm-hmm" as "Amen." and took it for an interruption. Callback counts this as a *false yield*. |
| `good-false-yield-amen-before-fix.mp3` | The call in the figure. Listen for the "mm-hmm" at 2.1 s and the agent going quiet. |
| `good-same-seed-after-fix.mp3` | The same call, same seed, after the agent was fixed: it talks straight through the "mm-hmm". |
| `buggy-false-yield.mp3` | The buggy agent stops dead 0.1 s after "mm-hmm" (2.1 s), and again after "okay" (9.8 s). |
| `buggy-barge-in-talks-over.mp3` | The caller cuts in at 4.4 s: "Sorry, it's for Saturday evening." The buggy agent keeps talking over them for 1.2 s before it stops. A well-behaved agent stops within about half a second. |

The figure was drawn from the full recording of the first call; the clips were cut from
the full recordings with `soundfile`.
