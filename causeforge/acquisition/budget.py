"""Execution budgets for acquisition (M2).

A budget is a hard ceiling on real execution spend — replays and/or
wall-seconds.  Policies decide *what* to run; the budget decides *when
the money runs out*, and it applies identically to every policy so
cost-per-unit comparisons are matched by construction.
"""
from __future__ import annotations

from dataclasses import dataclass

from causeforge.sdk.schemas import CostLedger


@dataclass
class Budget:
    max_replays: int | None = None
    max_seconds: float | None = None

    def exhausted(self, spent: CostLedger) -> bool:
        if self.max_replays is not None and spent.replay_runs >= self.max_replays:
            return True
        if self.max_seconds is not None and spent.wall_time_s >= self.max_seconds:
            return True
        return False

    def label(self) -> str:
        parts = []
        if self.max_replays is not None:
            parts.append(f"{self.max_replays} replays")
        if self.max_seconds is not None:
            parts.append(f"{self.max_seconds:.0f}s")
        return " / ".join(parts) or "unlimited"
