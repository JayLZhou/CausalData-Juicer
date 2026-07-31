"""Minimal causal slicing via delta debugging (ddmin).

Given a validated (flipping) intervention, find the minimal subset of its
atoms (per-arg / per-line edits) that still flips the outcome.  Every
probe is a real replay and is charged to the unit's ledger — slicing cost
is part of the unit's acquisition cost, not free.
"""
from __future__ import annotations

from typing import Callable, Sequence, TypeVar

from causal_data_juicer.interventions.apply import intervention_atoms, rebuild_from_atoms
from causal_data_juicer.replay.replayer import Replayer
from causal_data_juicer.sdk.schemas import (
    CausalUnit,
    Episode,
    EvidenceTier,
    Intervention,
    InterventionType,
    Snapshot,
)

T = TypeVar("T")


def ddmin(atoms: Sequence[T], test: Callable[[list[T]], bool]) -> list[T]:
    """Classic ddmin: smallest subset of ``atoms`` for which test() holds.
    Assumes test(atoms) is True."""
    atoms = list(atoms)
    n = 2
    while len(atoms) >= 2:
        chunk = max(1, len(atoms) // n)
        subsets = [atoms[i : i + chunk] for i in range(0, len(atoms), chunk)]
        reduced = False
        for i, subset in enumerate(subsets):
            complement = [a for j, s in enumerate(subsets) if j != i for a in s]
            if complement and test(complement):
                atoms = complement
                n = max(n - 1, 2)
                reduced = True
                break
        if not reduced:
            if n >= len(atoms):
                break
            n = min(len(atoms), n * 2)
    return atoms


def minimize_unit(
    replayer: Replayer,
    episode: Episode,
    snapshots: list[Snapshot],
    unit: CausalUnit,
) -> CausalUnit:
    """Slice a REPRODUCIBLE unit down to its minimal intervention and
    promote it to MINIMAL (re-validated after slicing)."""
    if unit.tier < EvidenceTier.REPRODUCIBLE:
        return unit
    iv = unit.intervention
    atoms = intervention_atoms(iv)
    unit.atoms_before_slicing = max(1, len(atoms))

    if iv.type == InterventionType.ACTION_REPLACE or len(atoms) <= 1:
        # Already atomic: one confirmation replay promotes it.
        outcome = replayer.intervened_flip(episode, snapshots, iv, unit.cost)
        if outcome.success:
            unit.minimal_intervention = iv
            unit.atoms_after_slicing = unit.atoms_before_slicing
            unit.tier = EvidenceTier.MINIMAL
        return unit

    def flips(subset: list) -> bool:
        sub = rebuild_from_atoms(iv, subset)
        outcome = replayer.intervened_flip(episode, snapshots, sub, unit.cost)
        return outcome.success

    minimal_atoms = ddmin(atoms, flips)
    minimal = rebuild_from_atoms(iv, minimal_atoms)
    # Final re-validation of the sliced intervention.
    if replayer.intervened_flip(episode, snapshots, minimal, unit.cost).success:
        unit.minimal_intervention = minimal
        unit.atoms_after_slicing = len(minimal_atoms)
        unit.tier = EvidenceTier.MINIMAL
    return unit
