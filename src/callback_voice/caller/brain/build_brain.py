import hashlib
from pathlib import Path

from callback_voice.caller.brain.base import CallerBrain
from callback_voice.caller.brain.cassette_brain import CassetteBrain
from callback_voice.caller.brain.persona_brain import PersonaBrain
from callback_voice.caller.brain.scripted_brain import ScriptedBrain
from callback_voice.core.config.project_config import RecordedMode
from callback_voice.core.models.scenario import Scenario
from callback_voice.providers.llm.base import ChatModel


def build_brain(
    scenario: Scenario,
    *,
    seed: int,
    recorded: RecordedMode,
    cassette_dir: Path,
    llm: ChatModel | None,
    temperature: float = 0.7,
) -> CallerBrain:
    """The caller's brain for one trial: scripted, live LLM, recording, or replaying.

    ``auto`` replays when a cassette for this exact caller and seed exists, and
    records otherwise.
    """
    spec = scenario.caller
    if spec.script is not None:
        return ScriptedBrain(spec.script)
    spec_hash = hashlib.sha256(spec.model_dump_json().encode()).hexdigest()[:10]
    path = cassette_dir / scenario.id / f"seed-{seed}-{spec_hash}.json"
    mode = "replay" if recorded == "replay" or (recorded == "auto" and path.is_file()) else "record"
    if mode == "replay":
        return CassetteBrain(path, "replay")
    if llm is None:
        raise RuntimeError("an LLM is required to record a caller")
    live = PersonaBrain(llm, spec, seed=seed, temperature=temperature)
    return live if recorded == "off" else CassetteBrain(path, "record", live)
