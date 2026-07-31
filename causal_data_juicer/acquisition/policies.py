"""Pluggable acquisition policies (M2 strategy layer).

A policy orders the candidate queue and may stop early; it never touches
execution itself — mechanisms (control memoization, early repro stop,
caching) and the budget apply identically underneath every policy, so a
user-supplied strategy competes on the same metered ground as ours.

Shipped policies:
  exhaustive  validate everything in given order (baseline)
  random      shuffled order (baseline, seedable)
  adaptive    default optimizer:
              1. adaptive singleton — episodes without a validated unit
                 come first (a second unit on the same episode is worth
                 less than a first unit on an uncovered one);
              2. family-level UCB1 on observed flip yield — spend where
                 flips happen, keep exploring elsewhere;
              3. source diversity per episode (A10: heterogeneous fixer
                 pools cover more than any single source).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional, Protocol

from causal_data_juicer.sdk.schemas import CausalUnit, Episode, Intervention


@dataclass
class Candidate:
    episode: Episode
    intervention: Intervention

    @property
    def family(self) -> str:
        return self.episode.meta.get("family", self.episode.task_id.split("_")[0])


class AcquisitionPolicy(Protocol):
    name: str

    def next(self, pending: list[Candidate]) -> Optional[Candidate]:
        """Pick the next candidate from ``pending`` (None = stop early)."""

    def observe(self, candidate: Candidate, unit: CausalUnit) -> None:
        ...


@dataclass
class ExhaustivePolicy:
    name: str = "exhaustive"

    def next(self, pending: list[Candidate]) -> Optional[Candidate]:
        return pending[0] if pending else None

    def observe(self, candidate: Candidate, unit: CausalUnit) -> None:
        pass


@dataclass
class RandomPolicy:
    seed: int = 0
    name: str = "random"

    def __post_init__(self):
        self._rng = random.Random(self.seed)

    def next(self, pending: list[Candidate]) -> Optional[Candidate]:
        return self._rng.choice(pending) if pending else None

    def observe(self, candidate: Candidate, unit: CausalUnit) -> None:
        pass


@dataclass
class AdaptivePolicy:
    name: str = "adaptive"
    explore: float = 2.0
    attempted_episodes: set = field(default_factory=set)
    family_trials: dict = field(default_factory=dict)
    family_flips: dict = field(default_factory=dict)
    tried_sources: dict = field(default_factory=dict)  # episode_id -> set(source)
    total_trials: int = 0

    def _ucb(self, family: str) -> float:
        n = self.family_trials.get(family, 0)
        if n == 0:
            return float("inf")  # optimism: never-tried families first
        mean = self.family_flips.get(family, 0) / n
        return mean + math.sqrt(self.explore * math.log(max(2, self.total_trials)) / n)

    def next(self, pending: list[Candidate]) -> Optional[Candidate]:
        if not pending:
            return None

        def priority(c: Candidate):
            # adaptive singleton: breadth first — one candidate per episode
            # before anyone's second candidate
            singleton = c.episode.id not in self.attempted_episodes
            new_source = c.intervention.source not in self.tried_sources.get(c.episode.id, set())
            return (singleton, self._ucb(c.family), new_source)

        return max(pending, key=priority)

    def observe(self, candidate: Candidate, unit: CausalUnit) -> None:
        self.total_trials += 1
        family = candidate.family
        self.family_trials[family] = self.family_trials.get(family, 0) + 1
        self.family_flips[family] = self.family_flips.get(family, 0) + int(unit.flipped)
        self.tried_sources.setdefault(candidate.episode.id, set()).add(
            candidate.intervention.source)
        self.attempted_episodes.add(candidate.episode.id)


def make_policy(spec: str) -> AcquisitionPolicy:
    if spec == "exhaustive":
        return ExhaustivePolicy()
    if spec.startswith("random"):
        seed = int(spec.split(":", 1)[1]) if ":" in spec else 0
        return RandomPolicy(seed=seed, name=spec)
    if spec == "adaptive":
        return AdaptivePolicy()
    raise ValueError(f"unknown policy: {spec}")
