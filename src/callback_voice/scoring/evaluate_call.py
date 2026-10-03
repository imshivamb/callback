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
from callback_voice.scoring.metrics.folded_turns import fold_unanswered
from callback_voice.scoring.metrics.policy_rules import policy_rules
from callback_voice.scoring.metrics.task_success import task_success
from callback_voice.scoring.score_call import score_call
from callback_voice.scoring.timeline.speech_turns import speech_turns
from callback_voice.scoring.transcript.build_transcript import build_transcript


@dataclass(frozen=True, slots=True)
class CallEvaluation:
    metrics: list[Metric]
    findings: list[Finding]
    transcript: list[Turn]
    review: list[ReviewItem]
    speech: list[Turn]


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
    unanswered = any(f.metric == "unanswered_turns" for f in timing.findings)
    needs_words = bool(expect.entities_spoken or expect.must_not or judge is not None or unanswered)
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
    judging = judge is not None and bool(transcript)
    unchecked = [] if judging else judged_rules
    results = [
        task_success(state, expect.thresholds.task_success_rate, timing.timeline.duration_s),
        entity_fidelity(facts, expect.thresholds.entity_fidelity),
        policy_rules(
            transcript,
            rule_checks,
            expect.thresholds.policy_violations,
            not_checked=len(unchecked),
        ),
    ]
    if judge is not None and judging:
        results.append(await judge_call(judge, transcript, judged_rules))

    timing_metrics, timing_findings = timing.metrics, timing.findings
    if unanswered and transcript:
        timing_metrics, timing_findings = fold_unanswered(
            timing_metrics,
            timing_findings,
            timing.timeline.utterances,
            transcript,
            expect.thresholds.unanswered_turns,
        )
    metrics = [*timing_metrics, *(m for r in results for m in r.metrics)]
    if unchecked:
        # Never let a rule that could not be checked read like one that passed.
        why = "no judge is configured (providers.judge)" if judge is None else "no transcript"
        metrics.append(
            Metric(
                name="rules_not_checked",
                value=len(unchecked),
                unit="count",
                method="judge",
                detail=f"{len(unchecked)} plain-English rule(s) not checked: {why}",
            )
        )
    findings = sorted(
        [*timing_findings, *(f for r in results for f in r.findings)], key=lambda f: f.t_s
    )
    speech = speech_turns(timing.timeline, transcript)
    return CallEvaluation(metrics, findings, transcript, review, speech)
