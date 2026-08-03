"""Selective revalidation under real dependency-version events (M4).

A version event (upgrade or rollback of one family's pin) invalidates
the *claims* of causal units whose dependency closure includes that
family — and only those.  Revalidation replays each targeted unit's
paired counterfactual inside the *new* environment (env-pointer override
at fork time) and either:

  CONFIRMED  control still reproduces AND fix still flips n/n
             -> tier kept, provenance re-stamped to the new env;
  DEMOTED    'control-drift'   the original failure itself no longer
                               reproduces (the episode went stale), or
             'fix-broken'      the fix no longer flips
             -> tier drops to SUGGESTED with the reason recorded.

``mode=selective`` touches only units whose provenance claims the
changed family; ``mode=full`` is the ground-truth baseline that touches
everything.  The A8 numbers are the replay ratio between the two and
the demotion-set agreement (selective must not miss any demotion that
full finds).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from causal_data_juicer.maintenance.provenance import needs_revalidation
from causal_data_juicer.replay.replayer import Replayer
from causal_data_juicer.runtime.envs import EnvManager, TaskEnv, write_env_pointer
from causal_data_juicer.run_store import RunStore
from causal_data_juicer.sdk.schemas import CausalUnit, Episode, EvidenceTier, Snapshot, digest_of


def load_pooled_units(base_dir: Path, pool_dirs: list[Path]):
    """Validated units from base + pool runs, remapped onto base episodes."""
    base = RunStore(base_dir)
    episodes = base.load_episodes()
    snapshots = base.load_snapshots()
    by_task = {ep.task_id: ep for ep in episodes}
    units, seen = [], set()
    for run_dir in [base_dir, *pool_dirs]:
        for u in RunStore(run_dir).load_units():
            ep = by_task.get(u.task_id)
            if ep is None or u.tier < EvidenceTier.COUNTERFACTUAL_VALIDATED:
                continue
            key = f"{ep.id}:{u.effective_intervention().effect_signature()}"
            if key in seen:
                continue
            seen.add(key)
            u.episode_id = ep.id  # remap pool units onto base episodes
            units.append(u)
    return base, episodes, snapshots, units


def enrich_dependency_claims(units: list[CausalUnit], family_of_task: dict[str, str],
                             env_freezes: dict[str, str]) -> None:
    """Backfill per-family dependency claims on units stamped before M4."""
    for u in units:
        family = u.provenance.get("family") or family_of_task[u.task_id]
        u.provenance["family"] = family
        u.provenance.setdefault(f"env:{family}", env_freezes[family])


@dataclass
class ModeReport:
    mode: str
    considered: int = 0
    revalidated: int = 0
    confirmed: int = 0
    demoted: list[dict] = field(default_factory=list)
    replays: int = 0
    seconds: float = 0.0


def revalidate(
    units: list[CausalUnit],
    episodes: list[Episode],
    snapshots: list[Snapshot],
    replayer: Replayer,
    changed_family: str,
    new_env_python: Path,
    new_env_freeze: str,
    old_freezes: dict[str, str],
    mode: str,
    n_repro: int = 2,
) -> ModeReport:
    eps = {ep.id: ep for ep in episodes}
    current = {f"env:{fam}": frz for fam, frz in old_freezes.items()}
    current[f"env:{changed_family}"] = new_env_freeze

    report = ModeReport(mode=mode, considered=len(units))
    targets = [u for u in units if needs_revalidation(u, current)] if mode == "selective" \
        else list(units)
    control_cache: dict = {}
    t0 = time.monotonic()
    for u in targets:
        affected = u.provenance.get("family") == changed_family
        prep = (lambda ws: write_env_pointer(ws, new_env_python)) if affected else None
        fresh = replayer.paired_replay(
            eps[u.episode_id], snapshots, u.effective_intervention(),
            n_repro=n_repro, control_cache=control_cache,
            early_stop_repro=True, prep=prep,
        )
        report.revalidated += 1
        report.replays += fresh.cost.replay_runs
        if fresh.original_replay_match is False:
            u.tier = EvidenceTier.SUGGESTED
            u.provenance["stale_reason"] = "control-drift"
            report.demoted.append({"unit_id": u.id, "task_id": u.task_id,
                                   "reason": "control-drift"})
        elif fresh.flipped and fresh.repro_flips == fresh.repro_runs:
            report.confirmed += 1
            if affected:
                u.provenance[f"env:{changed_family}"] = new_env_freeze
        else:
            u.tier = EvidenceTier.SUGGESTED
            u.provenance["stale_reason"] = "fix-broken"
            report.demoted.append({"unit_id": u.id, "task_id": u.task_id,
                                   "reason": "fix-broken"})
    report.seconds = round(time.monotonic() - t0, 2)
    return report


def run_version_event(
    base_dir: Path,
    pool_dirs: list[Path],
    family_name: str,
    new_pin: str,
    env_root: Path,
    n_repro: int = 2,
) -> dict:
    from causal_data_juicer.replay.sandbox import UnsafeLocalWorkspace
    from causal_data_juicer.runtime.tools import default_registry
    from causal_data_juicer.runtime.verifier import PytestVerifier
    from causal_data_juicer.workloads.depmig.build import enabled_families

    base, episodes, snapshots, units = load_pooled_units(base_dir, pool_dirs)
    mgr = EnvManager(env_root)
    families = {fam.name: fam for fam, _ in enabled_families()}
    family_of_task = {t.id: fam.name for fam, ts in enabled_families() for t in ts}
    old_freezes = {name: digest_of(mgr.provenance(fam.new_env()).get("frozen", []))
                   for name, fam in families.items()}
    enrich_dependency_claims(units, family_of_task, old_freezes)

    version = new_pin.split("==")[-1].replace(".", "-")
    new_env = TaskEnv(name=f"{family_name}-reval-{version}", packages=[new_pin])
    new_python = mgr.ensure(new_env)
    new_freeze = digest_of(mgr.provenance(new_env).get("frozen", []))

    replayer = Replayer(default_registry(),
                        UnsafeLocalWorkspace(base.blobs, Path(base_dir) / "scratch-m4"),
                        PytestVerifier(timeout=120))
    modes = {}
    for mode in ("selective", "full"):
        # fresh copies so the two modes don't see each other's demotions
        _, _, _, fresh_units = load_pooled_units(base_dir, pool_dirs)
        enrich_dependency_claims(fresh_units, family_of_task, old_freezes)
        modes[mode] = revalidate(fresh_units, episodes, snapshots, replayer,
                                 family_name, new_python, new_freeze, old_freezes,
                                 mode, n_repro=n_repro)

    sel, full = modes["selective"], modes["full"]
    agreement = sorted(d["unit_id"] for d in sel.demoted) == \
        sorted(d["unit_id"] for d in full.demoted)
    return {
        "event": {"family": family_name, "new_pin": new_pin},
        "units_total": len(units),
        "selective": sel.__dict__,
        "full": full.__dict__,
        "replay_ratio": round(full.replays / max(1, sel.replays), 2),
        "demotion_agreement": agreement,
    }
