import json
from typing import Any

from callback_voice.caller.brain.base import CallerLine
from callback_voice.caller.brain.parse_brain_reply import parse_brain_reply
from callback_voice.caller.brain.persona_prompt import persona_prompt
from callback_voice.core.models.caller_spec import CallerSpec
from callback_voice.providers.llm.base import ChatMessage, ChatModel

_MAX_TURNS = 24
_SILENT_AGENT = "(The call has connected. Nobody has spoken yet.)"


class PersonaBrain:
    """An LLM playing the scenario's caller, one line per agent turn.

    The LLM sees the agent's transcribed words as the user side of the chat and its
    own earlier replies as the assistant side. Anything the caller said outside that
    loop (a chaos barge-in, a changed mind) is added as a note before the next agent
    message so the persona stays consistent.
    """

    needs_agent_text = True

    def __init__(
        self, llm: ChatModel, spec: CallerSpec, *, seed: int, temperature: float = 0.7
    ) -> None:
        self._llm = llm
        self._seed = seed
        self._temperature = temperature
        self._messages = [ChatMessage("system", persona_prompt(spec))]
        self._notes: list[str] = []
        self._turns = 0
        self.input_tokens = 0
        self.output_tokens = 0

    async def next_line(self, agent_said: str) -> CallerLine | None:
        if self._turns >= _MAX_TURNS:
            return None
        heard = agent_said.strip() or _SILENT_AGENT
        if self._notes:
            heard = " ".join(self._notes) + "\n" + heard
            self._notes.clear()
        self._messages.append(ChatMessage("user", heard))
        completion = await self._llm.complete(
            self._messages,
            temperature=self._temperature,
            seed=self._seed + self._turns,
            max_tokens=300,
            json_mode=True,
        )
        self.input_tokens += completion.input_tokens
        self.output_tokens += completion.output_tokens
        line = parse_brain_reply(completion.text)
        self._messages.append(
            ChatMessage(
                "assistant",
                json.dumps(
                    {"say": line.text, "goal_reached": line.goal_reached, "hang_up": line.hang_up}
                ),
            )
        )
        self._turns += 1
        if not line.text and not line.hang_up:
            return CallerLine("Sorry, could you say that again?")
        return line

    def note_interjection(self, text: str) -> None:
        self._notes.append(f'[You also said: "{text}"]')

    def apply_updates(self, updates: dict[str, Any]) -> None:
        changes = ", ".join(f"{k} is now {v}" for k, v in updates.items())
        self._notes.append(f"[Your plans changed: {changes}.]")

    @property
    def usd_spent(self) -> float:
        return (self.input_tokens + self.output_tokens) / 1000 * self._llm.usd_per_1k_tokens
