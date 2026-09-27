from callback_voice.audio.format import SAMPLE_RATE, Audio
from callback_voice.core.models.expected_fact import ExpectedFact
from callback_voice.core.models.turn import Turn
from callback_voice.providers.stt.base import SpeechToText
from callback_voice.scoring.facts.fact_result import FactResult
from callback_voice.scoring.facts.locate_difference import locate_difference
from callback_voice.scoring.facts.match_fact import FactMatch, match_fact
from callback_voice.scoring.facts.noisiness import noisiness
from callback_voice.scoring.facts.word_confidence import fact_word_confidence

SURE_WORD_P = 0.5
NOISY_FLATNESS = 0.5
SURE_TURN_P = 0.55
_PAD_S = 0.1


async def check_facts(
    facts: tuple[ExpectedFact, ...],
    transcript: list[Turn],
    agent_audio: Audio,
    careful_stt: SpeechToText | None,
    language: str | None,
) -> list[FactResult]:
    """Decide, for each expected fact, whether the agent said it correctly.

    A fact the transcript shows as a near miss is only called *wrong* when the audio
    at the differing character is voice (not noise), the recogniser was sure of those
    words, and a second, more careful transcription of the same turn hears the same
    wrong value. A partial match (characters missing) is always uncertain. Otherwise it is *uncertain*: the fault
    may be the transcription's, so a person should listen. A fact never mentioned is
    *missing*, unless the whole transcript is low-confidence (then uncertain).
    """
    agent_turns = [t for t in transcript if t.speaker == "agent"]
    results: list[FactResult] = []
    for fact in facts:
        matches = [(turn, match_fact(fact, turn.text)) for turn in agent_turns]
        said = next((t for t, m in matches if m.status == "said"), None)
        if said is not None:
            results.append(
                FactResult(fact, "correct", None, said.start_s, said.end_s, "said correctly")
            )
            continue
        near = next(((t, m) for t, m in matches if m.status == "near_miss"), None)
        if near is not None:
            results.append(await _judge_near_miss(fact, *near, agent_audio, careful_stt, language))
            continue
        scores = [t.confidence for t in agent_turns if t.confidence is not None]
        first = agent_turns[0].start_s if agent_turns else 0.0
        if scores and sum(scores) / len(scores) < SURE_TURN_P:
            results.append(
                FactResult(
                    fact,
                    "uncertain",
                    None,
                    first,
                    None,
                    "not found, but the transcript itself is low-confidence",
                )
            )
        else:
            results.append(FactResult(fact, "missing", None, first, None, "never said"))
    return results


async def _judge_near_miss(
    fact: ExpectedFact,
    turn: Turn,
    match: FactMatch,
    agent_audio: Audio,
    careful_stt: SpeechToText | None,
    language: str | None,
) -> FactResult:
    heard = match.heard
    if match.partial:
        return FactResult(
            fact,
            "uncertain",
            heard,
            turn.start_s,
            turn.end_s,
            f"heard only part of it ({heard}); the transcription may have dropped a sound",
        )
    window = locate_difference(turn, heard or "", fact.value)
    noise = noisiness(agent_audio, *window) if window else None
    if noise is not None and noise > NOISY_FLATNESS:
        return FactResult(
            fact,
            "uncertain",
            heard,
            turn.start_s,
            turn.end_s,
            f"the audio where it differs is noise-like (flatness {noise:.2f}); "
            "the line may have swallowed the sound",
        )
    confidence = fact_word_confidence(turn, heard or "")
    if confidence is not None and confidence < SURE_WORD_P:
        return FactResult(
            fact,
            "uncertain",
            heard,
            turn.start_s,
            turn.end_s,
            f"transcription unsure of these words (confidence {confidence:.2f})",
        )
    if careful_stt is not None:
        start = max(0, round((turn.start_s - _PAD_S) * SAMPLE_RATE))
        end = round((turn.end_s + _PAD_S) * SAMPLE_RATE)
        second = await careful_stt.transcribe(agent_audio[start:end], language=language)
        again = match_fact(fact, second.text)
        if again.status != "near_miss" or again.heard != heard:
            return FactResult(
                fact,
                "uncertain",
                heard,
                turn.start_s,
                turn.end_s,
                f"two transcriptions disagree (first heard {heard}, second "
                f"{'the expected value' if again.status == 'said' else again.heard or 'nothing'})",
            )
    return FactResult(fact, "wrong", heard, turn.start_s, turn.end_s, "said a different value")
