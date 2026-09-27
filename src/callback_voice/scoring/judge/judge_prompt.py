from typing import Final

from callback_voice.core.models.turn import Turn
from callback_voice.providers.llm.base import ChatMessage

JUDGE_PROMPT_VERSION: Final = "judge-v1"

_SYSTEM = """You review a recorded phone call between a CALLER and an automated voice AGENT.
The transcript was produced by speech recognition, so expect small transcription errors;
do not penalise the agent for those.

Judge only what the transcript shows. For each rule, decide whether the AGENT broke it.
Quote the agent's exact words as evidence when it did.

Then rate the agent's conversational quality from 1 (poor) to 5 (excellent):
- concise: short, clear turns without filler
- no_repetition: does not repeat itself or loop
- handles_frustration: stays calm and helpful when the caller is impatient or confused

Reply with only this JSON object:
{"rules": [{"rule": "<rule text>", "violated": true|false, "evidence": "<quote or empty>", "at_s": <number or null>}],
 "experience": {"concise": 1-5, "no_repetition": 1-5, "handles_frustration": 1-5, "summary": "<one sentence>"}}"""


def judge_messages(transcript: list[Turn], rules: list[str]) -> list[ChatMessage]:
    """The judge's input: a timestamped transcript and the plain-text rules."""
    lines = "\n".join(
        f"[{t.start_s:6.1f}s] {t.speaker.upper()}: {t.text}" for t in transcript if t.text
    )
    listed = "\n".join(f"- {rule}" for rule in rules) or "- (no rules; only rate experience)"
    return [
        ChatMessage("system", _SYSTEM),
        ChatMessage("user", f"Rules the agent must not break:\n{listed}\n\nTranscript:\n{lines}"),
    ]
