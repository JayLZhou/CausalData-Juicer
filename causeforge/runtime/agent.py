"""Agent policies for M1.

``ScriptedPolicy`` is a deterministic mock-LLM agent: each step's action
and the "model response" that produced it are fixed by the workload
script.  This keeps the M1 loop fully deterministic (the flip-reproducibility
kill line is measured on this deterministic subset) while exercising the
exact same recording surface a live LLM agent would.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from causeforge.sdk.schemas import LLMRecord, Step, ToolCall


def _mock_tokens(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass
class ScriptedStep:
    action: ToolCall
    thought: str = ""


class ScriptedPolicy:
    """Replays a fixed action script, emitting cached mock-LLM records."""

    def __init__(self, script: list[ScriptedStep], model: str = "mock-llm"):
        self.script = script
        self.model = model

    def next_action(
        self, task_id: str, step_index: int, history: list[Step]
    ) -> Optional[tuple[ToolCall, Optional[LLMRecord]]]:
        if step_index >= len(self.script):
            return None
        s = self.script[step_index]
        prompt = f"[task={task_id} step={step_index}] history={len(history)} steps"
        response = s.thought or f"call {s.action.tool}"
        llm = LLMRecord(
            model=self.model,
            prompt=prompt,
            response=response,
            tokens_in=_mock_tokens(prompt),
            tokens_out=_mock_tokens(response),
        )
        return s.action, llm
