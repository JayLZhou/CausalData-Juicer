"""Candidate screening (M1 baseline version).

Selects failed episodes and gathers candidate interventions from
registered sources, deduplicating by effect signature.  The budgeted
acquisition optimizer (adaptive singleton, sequential stopping) is M2;
this module only fixes the interface it will slot into.

M1 candidate source: a fix table shipped with the workload, standing in
for a cached fixer-LLM (zero live-token cost, which is exactly the cost
model recorded in the ledger).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from causeforge.sdk.schemas import Episode, EvidenceTier, Intervention


class CandidateSource(Protocol):
    def propose(self, episode: Episode) -> list[Intervention]:
        ...


@dataclass
class TableFixSource:
    """task_id -> candidate interventions (simulated cached fixer-LLM)."""

    table: dict[str, list[Intervention]] = field(default_factory=dict)
    name: str = "fixer-cache"

    def propose(self, episode: Episode) -> list[Intervention]:
        out = []
        for iv in self.table.get(episode.task_id, []):
            iv = iv.model_copy(deep=True)
            iv.source = self.name
            out.append(iv)
        return out


@dataclass
class Screener:
    sources: list[CandidateSource]

    def screen(self, episodes: list[Episode]) -> list[tuple[Episode, Intervention]]:
        candidates: list[tuple[Episode, Intervention]] = []
        seen: set[str] = set()
        for ep in episodes:
            if ep.outcome is None or ep.outcome.success:
                continue  # only failed episodes are intervention targets in M1
            for source in self.sources:
                for iv in source.propose(ep):
                    key = f"{ep.id}:{iv.effect_signature()}"
                    if key in seen:
                        continue  # effect-signature dedup
                    seen.add(key)
                    candidates.append((ep, iv))
        return candidates
