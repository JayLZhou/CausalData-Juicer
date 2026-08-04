"""Live-LLM agent policy speaking the same recording surface as the
scripted mock: every step yields (ToolCall, LLMRecord), so collector,
replay and exports need no changes when the agent gets real.

Protocol: the model answers with a single JSON object
``{"tool": "...", "args": {...}}``; ``{"tool": "done"}`` ends the episode.
"""

from __future__ import annotations

import json

from causal_data_juicer.runtime.llm import LLMClient
from causal_data_juicer.sdk.schemas import LLMRecord, Step, ToolCall

SYSTEM_PROMPT = """\
You are a coding agent working inside an isolated workspace.
Available tools (respond with EXACTLY one JSON object, nothing else):
  {"tool": "read_file",  "args": {"path": "<relative path>"}}
  {"tool": "write_file", "args": {"path": "<relative path>", "content": "<full file content>"}}
  {"tool": "run_pytest", "args": {}}
  {"tool": "done",       "args": {}}
Rules: never modify test files; always write complete file contents;
run the tests after editing; reply {"tool": "done", "args": {}} once tests pass
or when you cannot make further progress."""


def extract_action(text: str) -> dict | None:
    """First balanced JSON object in the reply (tolerates ``` fences and
    reasoning-model <think> blocks, which are stripped first)."""
    import re

    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    if "<think>" in text:  # unclosed block: reply truncated mid-thought
        text = text.split("<think>")[0]
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start : i + 1])
                        if isinstance(obj, dict) and "tool" in obj:
                            return obj
                    except json.JSONDecodeError:
                        break
                    break
        start = text.find("{", start + 1)
    return None


class LLMPolicy:
    def __init__(
        self,
        llm: LLMClient,
        max_steps: int = 12,
        obs_limit: int = 2000,
        system_prompt: str = SYSTEM_PROMPT,
    ):
        self.llm = llm
        self.max_steps = max_steps
        self.obs_limit = obs_limit
        self.system_prompt = system_prompt
        self.task_description = ""

    def bind_task(self, description: str) -> None:
        self.task_description = description

    def _messages(self, history: list[Step]) -> list[dict]:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Task: {self.task_description}"},
        ]
        for step in history:
            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps(step.action.model_dump(), ensure_ascii=False),
                }
            )
            # Keep the tail: pytest puts the informative part at the end.
            messages.append(
                {"role": "user", "content": f"Observation: {step.observation[-self.obs_limit :]}"}
            )
        return messages

    def next_action(
        self, task_id: str, step_index: int, history: list[Step]
    ) -> tuple[ToolCall, LLMRecord | None] | None:
        if step_index >= self.max_steps:
            return None
        messages = self._messages(history)
        resp = self.llm.complete(messages)
        action = extract_action(resp.text)
        if action is None or action.get("tool") == "done":
            return None
        record = LLMRecord(
            model=self.llm.model,
            prompt=json.dumps(messages, ensure_ascii=False),
            response=resp.text,
            tokens_in=resp.tokens_in,
            tokens_out=resp.tokens_out,
            cached=resp.cached,
            dollars=resp.dollars,
        )
        return ToolCall(tool=action["tool"], args=action.get("args") or {}), record
