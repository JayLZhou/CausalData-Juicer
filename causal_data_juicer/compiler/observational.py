"""Observational compilation (Import Mode's product surface).

Without a replayable environment nothing can climb the evidence ladder,
but two honest products still exist — and every row says OBSERVED, the
floor of the ladder, instead of dressing up as causal data:

  bc_sft.jsonl       behavior cloning from *successful* trajectories
                     (per-step prompt -> action)
  failures.jsonl     failure log: task, trajectory tail, final outcome
                     (raw material for later intervention once the
                     project graduates to a replayable tier)
"""

from __future__ import annotations

from pathlib import Path

from causal_data_juicer.compiler.common import render_action, write_jsonl
from causal_data_juicer.sdk.schemas import Episode, EvidenceTier


def _context(episode: Episode, upto: int) -> str:
    lines = [f"Task: {episode.task_description}".strip()]
    for step in episode.steps[:upto]:
        lines.append(f"[step {step.index}] {render_action(step.action)}")
        lines.append(f"[obs {step.index}] {step.observation}")
    lines.append(f"[step {upto}] your next action:")
    return "\n".join(lines)


def compile_bc_sft(episodes: list[Episode], out: Path) -> Path:
    rows: list[dict] = []
    for ep in episodes:
        if ep.outcome is None or not ep.outcome.success:
            continue
        rows.extend(
            {
                "task_id": ep.task_id,
                "prompt": _context(ep, step.index),
                "completion": render_action(step.action),
                "evidence_tier": EvidenceTier.OBSERVED.name,
            }
            for step in ep.steps
        )
    return write_jsonl(out, rows)


def compile_failure_log(episodes: list[Episode], out: Path) -> Path:
    rows: list[dict] = []
    for ep in episodes:
        if ep.outcome is None or ep.outcome.success:
            continue
        rows.append(
            {
                "task_id": ep.task_id,
                "task": ep.task_description,
                "last_actions": [render_action(s.action) for s in ep.steps[-3:]],
                "outcome": ep.outcome.detail,
                "evidence_tier": EvidenceTier.OBSERVED.name,
            }
        )
    return write_jsonl(out, rows)


def compile_observational(episodes: list[Episode], out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    return {
        "bc_sft": compile_bc_sft(episodes, out_dir / "bc_sft.jsonl"),
        "failures": compile_failure_log(episodes, out_dir / "failures.jsonl"),
    }
