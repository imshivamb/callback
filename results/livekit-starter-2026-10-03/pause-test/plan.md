# Pause test: decided before running

Question: is the long end-of-turn wait on the line "I would like something vegetarian that
takes under thirty minutes." caused by the agent's turn detector or by the mid-line pause
in Callback's voice?

Setup: the hosted agent, unchanged except that its log level is raised to DEBUG
(`LIVEKIT_LOG_LEVEL`, added as an agent secret, which restarts it) so that the end-of-turn
probability is logged. One warm-up call first, excluded. Then 10 short calls, alternating
A and B so time of day cannot favour one: A has the line exactly as recorded (with the
pause), B has the same words, the same voice and the pause removed. Everything else is as in
the earlier runs. The caller speaks the first line, then this line, and the call ends after
the agent's reply.

Measures, per call:
1. Wait: from the end of the caller's speech to the agent committing the turn, from the
   agent's debug log, with the logged end-of-turn probability. Primary.
2. Excess reply delay: reply delay to this line minus reply delay to the first line of the
   same call, from Callback's recording. In the earlier hosted run the excess was a median
   1.38 s (0.68–1.66), and 1.23 s (0.25–1.79) on the laptop. Secondary.

Reading, fixed now:
- Caller artifact: A's median wait is at least 2.0 s and B's is 0.8 s or less. Report it as
  a Callback caveat and fix the voice.
- Agent finding: B's median wait is at least 2.0 s. The turn detector misjudges the
  sentence.
- Anything else, including A not reproducing a wait of 2.0 s or more: inconclusive; report
  the numbers.
