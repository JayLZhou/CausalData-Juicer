"""Import Mode ingestion (the lowest of the three access tiers).

External projects hand us traces they already have — no replayable
environment, no snapshots — as JSONL in a minimal generic schema:

    {"task_id": "...", "description": "...", "success": true|false,
     "steps": [{"tool": "...", "args": {...}, "observation": "..."}],
     "meta": {...}}                                     (meta optional)

They become first-class ``Episode`` objects whose evidence can never
exceed the observational ceiling: nothing here was validated by
intervention, and the tier system says so on every derived row.
"""
from __future__ import annotations

import json
from pathlib import Path

from causeforge.sdk.schemas import Episode, Outcome, Step, ToolCall, digest_of


def load_generic_traces(path: Path) -> list[Episode]:
    episodes = []
    for i, line in enumerate(Path(path).open()):
        if not line.strip():
            continue
        raw = json.loads(line)
        steps = []
        for j, s in enumerate(raw.get("steps", [])):
            action = ToolCall(tool=s["tool"], args=s.get("args", {}))
            obs = s.get("observation", "")
            steps.append(Step(index=j, action=action, observation=obs,
                              obs_digest=digest_of({"tool": action.tool, "obs": obs})))
        ep = Episode(
            task_id=raw.get("task_id", f"imported-{i}"),
            workload_id=raw.get("workload_id", "imported"),
            task_description=raw.get("description", ""),
            steps=steps,
            outcome=Outcome(success=bool(raw.get("success", False)),
                            detail=raw.get("outcome_detail", "")),
            meta={**raw.get("meta", {}), "import_mode": True},
        )
        episodes.append(ep)
    return episodes
