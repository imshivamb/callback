from dataclasses import dataclass
from pathlib import Path

from callback_voice.core.models.expectation import Expectation
from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric
from callback_voice.core.models.must_not_rule import MustNotRule
from callback_voice.core.models.review_item import ReviewItem
from callback_voice.core.models.turn import Turn
from callback_voice.core.models.verifier_result import VerifierResult
from callback_voice.providers.llm.base import ChatModel
from callback_voice.providers.stt.base import SpeechToText
from callback_voice.providers.vad.base import VoiceActivityModel
from callback_voice.scoring.facts.check_facts import check_facts
from callback_voice.scoring.judge.judge_call import judge_call
from callback_voice.scoring.load_call_audio import load_call_audio
from callback_voice.scoring.metrics.entity_fidelity import entity_fidelity
from callback_voice.scoring.metrics.policy_rules import policy_rules
from callback_voice.scoring.metrics.task_success import task_success
from callback_voice.scoring.score_call import score_call
from callback_voice.scoring.transcript.build_transcript import build_transcript


@dataclass(frozen=True, slots=True)
class CallEvaluation:
    metrics: list[Metric]
    findings: list[Finding]
    transcript: list[Turn]
    review: list[ReviewItem]


async def evaluate_call(
    call_dir: Path,
    expect: Expectation,
    *,
    vad: VoiceActivityModel,
    stt: SpeechToText | None,
    judge: ChatModel | None,
    state: VerifierResult | None,
    language: str | None,
    careful_stt: SpeechToText | None = None,
) -> CallEvaluation:
    """Everything known about one recorded call: timing, content, end state, judgement.

    Timing metrics need only VAD. The transcript (and so fact and policy checks)
    needs an STT; it is skipped when nothing asks for it. Facts the transcription is
    unsure about go to ``review`` instead of failing the agent. The judge only runs
    when configured.
    """
    timing = score_call(call_dir, expect.thresholds, vad)
    needs_words = bool(expect.entities_spoken or expect.must_not or judge is not None)
    agent_audio = load_call_audio(call_dir).agent
    transcript: list[Turn] = []
    if stt is not None and needs_words:
        transcript = await build_transcript(timing.timeline, agent_audio, stt, language)
    facts = (
        await check_facts(expect.entities_spoken, transcript, agent_audio, careful_stt, language)
        if transcript
        else []
    )
    review = [
        ReviewItem(check=f.fact.name, heard=f.heard, reason=f.reason, t_s=f.t_s, end_s=f.end_s)
        for f in facts
        if f.status == "uncertain"
    ]

    rule_checks = [r for r in expect.must_not if isinstance(r, MustNotRule)]
    judged_rules = [r for r in expect.must_not if isinstance(r, str)]
    results = [
        task_success(state, expect.thresholds.task_success_rate, timing.timeline.duration_s),
        entity_fidelity(facts, expect.thresholds.entity_fidelity),
        policy_rules(transcript, rule_checks, expect.thresholds.policy_violations),
    ]
    if judge is not None and transcript:
        results.append(await judge_call(judge, transcript, judged_rules))

    metrics = [*timing.metrics, *(m for r in results for m in r.metrics)]
    findings = sorted(
        [*timing.findings, *(f for r in results for f in r.findings)], key=lambda f: f.t_s
    )
    return CallEvaluation(metrics, findings, transcript, review)
