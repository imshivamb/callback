import traceback
from pathlib import Path

from callback_voice.caller.brain.build_brain import build_brain
from callback_voice.caller.engine.call_session import CallSession, CallSetup
from callback_voice.caller.speech.caller_speech import CallerSpeech
from callback_voice.chaos.build_processors import build_processors
from callback_voice.core.models.call_record import CallRecord
from callback_voice.core.models.scenario import Scenario
from callback_voice.core.models.trial_result import TrialResult
from callback_voice.core.runner.runtime import Runtime
from callback_voice.core.runner.trial_verdict import trial_verdict
from callback_voice.errors import CallbackError
from callback_voice.scoring.evaluate_call import evaluate_call
from callback_voice.scoring.verifiers.check_state import check_state
from callback_voice.scoring.verifiers.resolve_webhook import resolve_webhook
from callback_voice.transports.build_transport import build_transport


async def run_trial(
    scenario: Scenario, trial: int, seed: int, runtime: Runtime, run_dir: Path
) -> TrialResult:
    """Place one call, record it, score it offline and judge it.

    Any failure to run or score becomes ``error`` on the result, which the run
    reports with exit code 2: a broken call is never a pass.
    """
    call_id = f"{scenario.id}--t{trial}"
    call_dir = run_dir / "calls" / call_id
    try:
        target = runtime.project.targets[scenario.agent]
        brain = build_brain(
            scenario,
            seed=seed,
            recorded=runtime.recorded,
            cassette_dir=runtime.cassette_dir,
            llm=None if scenario.caller.script else runtime.llm,
        )
        setup = CallSetup(
            call_id=call_id,
            spec=scenario.caller,
            max_duration_s=scenario.max_duration_s,
            transport=build_transport(target),
            brain=brain,
            speech=CallerSpeech(runtime.tts, scenario.caller),
            make_vad=runtime.make_vad,
            stt=runtime.stt if brain.needs_agent_text else None,
            processors=tuple(
                build_processors(
                    scenario.chaos, seed, scenario.source.parent if scenario.source else Path()
                )
            ),
        )
        outcome = await CallSession(setup).run()
        paths = outcome.recorder.save(call_dir)
        outcome.log.save(call_dir / "events.jsonl")
        state = None
        if scenario.expect.state is not None:  # ask right away, while the call's state is fresh
            state = await check_state(
                scenario.expect.state,
                resolve_webhook(scenario.expect.state.webhook, target),
                call_id=call_id,
                scenario_id=scenario.id,
                trial=trial,
            )
        score = await evaluate_call(
            call_dir,
            scenario.expect,
            vad=runtime.make_vad(),
            stt=runtime.scoring_stt,
            careful_stt=runtime.careful_stt,
            judge=runtime.judge,
            state=state,
            language=scenario.caller.language,
        )
    except CallbackError as exc:
        return _errored(
            scenario, trial, seed, call_id, str(exc) + (f" ({exc.hint})" if exc.hint else "")
        )
    except Exception as exc:  # a bug must still surface as an error, not a pass
        return _errored(scenario, trial, seed, call_id, f"{exc!r}\n{traceback.format_exc(limit=6)}")

    passed, reasons = trial_verdict(score.metrics, score.findings, outcome.end_reason)
    record = CallRecord(
        call_id=call_id,
        scenario_id=scenario.id,
        trial=trial,
        seed=seed,
        transport=target.transport,
        started_at=outcome.started_at,
        duration_s=round(outcome.duration_s, 3),
        end_reason=outcome.end_reason,
        wav_path=str(paths.stereo.relative_to(run_dir)),
        events=outcome.log.events,
        transcript=score.transcript,
        speech=score.speech,
    )
    return TrialResult(
        call_id=call_id,
        scenario_id=scenario.id,
        trial=trial,
        seed=seed,
        passed=passed,
        metrics=score.metrics,
        findings=score.findings,
        failure_reasons=reasons,
        review=score.review,
        verifier_results=[state] if state is not None else [],
        call=record,
    )


def _errored(scenario: Scenario, trial: int, seed: int, call_id: str, message: str) -> TrialResult:
    return TrialResult(
        call_id=call_id,
        scenario_id=scenario.id,
        trial=trial,
        seed=seed,
        passed=False,
        error=message,
    )
