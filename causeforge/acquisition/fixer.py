"""LLM fixer candidate source for the depmig bench.

For a failed episode, ask the (cached) model for a corrected version of
the file the agent last wrote, and propose it as an ACTION_REPLACE at
that step.  The fixer sees exactly what an engineer would: the task
brief, the agent's final file, and the failing verifier output — never
the bench's answer key (migration_points stay hidden).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from causeforge.runtime.llm import LLMClient
from causeforge.runtime.llm_policy import extract_action
from causeforge.sdk.schemas import (
    CostLedger,
    Episode,
    Intervention,
    InterventionType,
    ToolCall,
)

FIXER_SYSTEM = """\
You are a senior engineer reviewing a failed coding-agent run.
You will get the task brief, the last file the agent wrote, and the failing
test output. Reply with EXACTLY one JSON object containing the corrected,
complete file: {"tool": "write_file", "args": {"path": "<same path>", "content": "<full corrected content>"}}
Do not change the path unless the path itself is the bug. No other text.
Constraint: ONLY the packages named in the task brief plus the standard
library are installed — importing any other third-party module (e.g. a
companion package) will fail. Prefer rewriting the code to use what is
available."""


def last_write_step(episode: Episode) -> int | None:
    for step in reversed(episode.steps):
        if step.action.tool == "write_file":
            return step.index
    return None


def propose_refinement(
    llm: LLMClient,
    episode: Episode,
    prior: Intervention,
    prior_failure: str,
    round_index: int,
    tests: dict | None = None,
    ledger: CostLedger | None = None,
) -> Intervention | None:
    """Validation-in-the-loop refinement: the fixer sees its own failed
    attempt AND the intervened branch's verifier output — feedback only a
    replay engine can provide — and proposes a revision."""
    k = prior.target_step
    step = episode.steps[k]
    tests_block = ""
    if tests:
        rendered = "\n\n".join(f"# {n}\n{c}" for n, c in tests.items())
        tests_block = f"\n\nRead-only test suite:\n```python\n{rendered}\n```"
    prior_content = (prior.new_action.args.get("content", "") if prior.new_action else "")
    messages = [
        {"role": "system", "content": FIXER_SYSTEM},
        {"role": "user", "content": (
            f"Task brief:\n{episode.task_description}\n\n"
            f"Original failing file ({step.action.args.get('path')}):\n"
            f"```python\n{step.action.args.get('content', '')}\n```\n"
            f"{tests_block}\n\n"
            f"Your previous fix (attempt {round_index}) was ACTUALLY EXECUTED and "
            f"still fails:\n```python\n{prior_content}\n```\n"
            f"Its verifier output:\n{prior_failure[-1200:]}\n\n"
            f"Diagnose why that attempt failed and propose a different fix."
        )},
    ]
    resp = llm.complete(messages)
    if ledger is not None and not resp.cached:
        ledger.charge_llm(resp.tokens_in, resp.tokens_out, dollars=resp.dollars)
    action = extract_action(resp.text)
    if not action or action.get("tool") != "write_file":
        return None
    args = action.get("args") or {}
    if not args.get("path") or not isinstance(args.get("content"), str):
        return None
    return Intervention(
        type=InterventionType.ACTION_REPLACE,
        target_step=k,
        new_action=ToolCall(tool="write_file",
                            args={"path": args["path"], "content": args["content"]}),
        rationale=f"refinement round {round_index} (validation-in-the-loop)",
        source=f"fixer-refine-r{round_index}",
    )


@dataclass
class FixerLLMSource:
    llm: LLMClient
    candidates_per_failure: int = 1
    name: str = "fixer-llm"
    ledger: CostLedger | None = None  # screening cost is acquisition cost
    # task_id -> {test filename: content}.  Tests are the spec; the agent
    # could read_file them too, so showing them to the fixer is a higher-
    # fidelity (costlier) prompt tier, not an answer key.
    tests_by_task: dict | None = None

    def propose(self, episode: Episode) -> list[Intervention]:
        k = last_write_step(episode)
        if k is None or episode.outcome is None:
            return []
        step = episode.steps[k]
        tests_block = ""
        if self.tests_by_task is not None:
            tests = self.tests_by_task.get(episode.task_id, {})
            if tests:
                rendered = "\n\n".join(f"# {name}\n{content}" for name, content in tests.items())
                tests_block = (f"\n\nThe (read-only) test suite defining expected "
                               f"behavior:\n```python\n{rendered}\n```")
        messages = [
            {"role": "system", "content": FIXER_SYSTEM},
            {"role": "user", "content": (
                f"Task brief:\n{episode.task_description}\n\n"
                f"Agent's last written file ({step.action.args.get('path')}):\n"
                f"```python\n{step.action.args.get('content', '')}\n```\n\n"
                f"Failing verifier output:\n{episode.outcome.detail}"
                f"{tests_block}"
            )},
        ]
        out: list[Intervention] = []
        for i in range(self.candidates_per_failure):
            msgs = messages if i == 0 else messages + [
                {"role": "user", "content": f"Give an alternative fix (variant {i})."}
            ]
            resp = self.llm.complete(msgs)
            if self.ledger is not None and not resp.cached:
                self.ledger.charge_llm(resp.tokens_in, resp.tokens_out, dollars=resp.dollars)
            action = extract_action(resp.text)
            if not action or action.get("tool") != "write_file":
                continue
            args = action.get("args") or {}
            if not args.get("path") or not isinstance(args.get("content"), str):
                continue
            out.append(Intervention(
                type=InterventionType.ACTION_REPLACE,
                target_step=k,
                new_action=ToolCall(tool="write_file", args={
                    "path": args["path"], "content": args["content"]}),
                rationale=f"fixer-llm candidate {i} (cached={resp.cached})",
                source=self.name,
            ))
        return out
