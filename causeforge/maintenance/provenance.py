"""Provenance stamping and selective revalidation (M1 slice of M4).

Every causal unit is stamped with the environment fingerprint it was
validated under.  ``needs_revalidation`` is the hook M4's selective
revalidation builds on: when a component version changes, only units
whose provenance mentions that component go back to the replay queue.
"""
from __future__ import annotations

import platform
import sys

from causeforge.runtime.tools import ToolRegistry
from causeforge.sdk.schemas import CausalUnit

CAUSEFORGE_VERSION = "0.1.0"


def env_fingerprint(registry: ToolRegistry, workload_id: str = "") -> dict:
    return {
        "causeforge": CAUSEFORGE_VERSION,
        "python": sys.version.split()[0],
        "platform": platform.system().lower(),
        "tool_registry": registry.fingerprint(),
        "workload": workload_id,
    }


def stamp(unit: CausalUnit, fingerprint: dict) -> CausalUnit:
    unit.provenance = dict(fingerprint)
    return unit


def needs_revalidation(unit: CausalUnit, current: dict) -> list[str]:
    """Components whose version drifted since the unit was validated.

    A unit's provenance is its *dependency claim*; ``current`` describes
    the world for the components the maintenance event tracks.  Only the
    intersection is compared: a component the unit never depended on
    (another family's env) or one outside the event's scope (production
    metadata like which fixer produced the unit) cannot trigger
    revalidation — that asymmetry is what makes it selective.
    """
    return [k for k in unit.provenance
            if k in current and current[k] != unit.provenance[k]]
