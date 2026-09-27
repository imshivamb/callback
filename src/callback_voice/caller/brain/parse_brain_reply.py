import json
import re

from callback_voice.caller.brain.base import CallerLine

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_STAGE_DIRECTIONS = re.compile(r"\*[^*]*\*|\([^)]*\)|\[[^\]]*\]")
_MAX_CHARS = 320
_FAREWELL = re.compile(
    r"\b(bye|goodbye|call (you )?back|take care|have a (good|great|nice))\b", re.I
)


def parse_brain_reply(raw: str) -> CallerLine:
    """Read the persona LLM's JSON reply, tolerating code fences and plain text.

    Whatever comes back is reduced to something speakable: stage directions and
    markdown are stripped and overly long lines are cut at a sentence boundary.
    """
    text = _FENCE.sub("", raw.strip()).strip()
    say, goal, hang_up = text, False, False
    try:
        data = json.loads(text[text.find("{") : text.rfind("}") + 1] if "{" in text else text)
        if isinstance(data, dict):
            say = str(data.get("say", ""))
            goal = bool(data.get("goal_reached", False))
            hang_up = bool(data.get("hang_up", False))
    except json.JSONDecodeError:
        pass
    say = re.sub(r"\s+", " ", _STAGE_DIRECTIONS.sub("", say)).replace("*", "").strip().strip('"')
    if len(say) > _MAX_CHARS:
        cut = say[:_MAX_CHARS]
        say = cut[: max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! ")) + 1] or cut
    # Models sometimes flag hang_up while still mid-task; only a farewell ends the call.
    if hang_up and not _FAREWELL.search(say):
        hang_up = False
    return CallerLine(say, hang_up=hang_up, goal_reached=goal)
