from callback_voice.core.models.finding import Finding
from callback_voice.core.models.metric import Metric
from callback_voice.core.models.turn import Turn
from callback_voice.scoring.metrics.metric_result import MetricResult
from callback_voice.text.near_miss_code import near_miss_code
from callback_voice.text.spoken_code_match import entity_spoken


def entity_fidelity(
    transcript: list[Turn], entities: tuple[str, ...], threshold: float
) -> MetricResult:
    """Share of expected entities the agent actually said correctly, from its own audio.

    Each entity must appear in the transcript of the agent channel, however it was
    spelled out. A near miss (e.g. BX7Q2 for DX7Q2) is reported with the wrong value.
    """
    if not entities:
        return MetricResult(metrics=[])
    agent_turns = [t for t in transcript if t.speaker == "agent"]
    findings: list[Finding] = []
    correct = 0
    for entity in entities:
        if any(entity_spoken(entity, t.text) for t in agent_turns):
            correct += 1
            continue
        wrong = next(
            ((t, miss) for t in agent_turns if (miss := near_miss_code(entity, t.text))), None
        )
        if wrong is not None:
            turn, miss = wrong
            findings.append(
                Finding(
                    metric="entity_fidelity",
                    t_s=turn.start_s,
                    end_s=turn.end_s,
                    message=f"The agent said “{' '.join(miss)}” instead of “{' '.join(entity)}”.",
                )
            )
        else:
            first = agent_turns[0].start_s if agent_turns else 0.0
            findings.append(
                Finding(
                    metric="entity_fidelity",
                    t_s=first,
                    severity="fail",
                    message=f"The agent never said “{entity}”.",
                )
            )
    value = round(correct / len(entities), 3)
    return MetricResult(
        metrics=[
            Metric(
                name="entity_fidelity",
                value=value,
                unit="ratio",
                threshold=threshold,
                comparator=">=",
                passed=value >= threshold,
                detail=f"{correct}/{len(entities)} expected entities spoken correctly",
            )
        ],
        findings=findings,
    )
