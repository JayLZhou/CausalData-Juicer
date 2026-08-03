"""M1.5 live pipeline: depmig bench + real LLM agent.

Same closed loop as the toy pipeline, with three additions:
  - per-family venv envs resolved through workspace pointers;
  - a live LLMPolicy (responses disk-cached) instead of the script;
  - anti-cheat post-check (spec §5): sealed test files and the env
    pointer must be byte-identical after the episode, else the episode
    is force-failed regardless of pytest's verdict.

Headline outputs: flip_repro_rate (kill line #1, real jackpot) and
control_digest_match_rate, both also broken down by family and tier.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from causal_data_juicer.acquisition.fixer import FixerLLMSource
from causal_data_juicer.acquisition.screener import Screener
from causal_data_juicer.compiler.exports import compile_all
from causal_data_juicer.maintenance.provenance import env_fingerprint, stamp
from causal_data_juicer.replay.replayer import Replayer
from causal_data_juicer.replay.sandbox import UnsafeLocalWorkspace
from causal_data_juicer.runtime.collector import Collector
from causal_data_juicer.runtime.envs import ENV_POINTER, EnvManager, write_env_pointer
from causal_data_juicer.runtime.llm import DiskCachedLLM, OpenAICompatClient
from causal_data_juicer.runtime.llm_policy import LLMPolicy
from causal_data_juicer.runtime.tools import default_registry
from causal_data_juicer.runtime.verifier import PytestVerifier
from causal_data_juicer.run_store import RunStore
from causal_data_juicer.sdk.schemas import CausalUnit, CostLedger, Episode, EvidenceTier, Snapshot
from causal_data_juicer.slicing.ddmin import minimize_unit
from causal_data_juicer.workloads.depmig.base import WORKLOAD_ID, DepMigTask
from causal_data_juicer.workloads.depmig.build import enabled_families


def _seal_check(task: DepMigTask, workspace: Path) -> str | None:
    """Return a violation message if sealed files were touched."""
    for rel, expected in task.test_files().items():
        p = workspace / rel
        if not p.exists() or p.read_text() != expected:
            return f"sealed test file modified: {rel}"
    if not (workspace / ENV_POINTER).exists():
        return "env pointer removed"
    return None


def run_depmig(
    run_dir: Path,
    base_url: str,
    model: str,
    n_repro: int = 3,
    max_steps: int = 10,
    task_ids: list[str] | None = None,
    env_root: Path = Path("bench_envs"),
    fixer_candidates: int = 1,
    fixer_base_url: str | None = None,
    fixer_model: str | None = None,
    llm_cache: Path | None = None,
    sources: str = "fixer",  # comma list: fixer, fixer-tests, resample
    resample_k: int = 3,
    resample_temperature: float = 0.85,
    refine_rounds: int = 0,  # validation-in-the-loop refinement for unflipped episodes
    episode_variants: int = 1,  # >1: extra prompt-perturbed episodes per task
    task_hints: dict | None = None,  # task_id -> text appended to the agent prompt (e.g. retrieved memory)
) -> dict:
    t_start = time.monotonic()
    from causal_data_juicer.runtime.rundir import prepare_run_dir
    run_dir = prepare_run_dir(Path(run_dir))
    store = RunStore(run_dir)
    registry = default_registry()
    verifier = PytestVerifier(timeout=120)
    collector = Collector(registry, store.blobs, verifier)
    sandbox = UnsafeLocalWorkspace(store.blobs, run_dir / "scratch")
    replayer = Replayer(registry, sandbox, verifier)
    mgr = EnvManager(env_root)
    cache_dir = Path(llm_cache) if llm_cache else run_dir / "llm_cache"
    llm = DiskCachedLLM(OpenAICompatClient(base_url, model), cache_dir)
    fixer_llm = llm
    if fixer_model and fixer_model != model:
        fixer_llm = DiskCachedLLM(
            OpenAICompatClient(fixer_base_url or base_url, fixer_model), cache_dir
        )

    tasks: list[tuple[DepMigTask, Path]] = []
    env_freezes: dict[str, str] = {}  # family -> pip-freeze digest
    for family, family_tasks in enabled_families():
        python = None
        for task in family_tasks:
            if task_ids and task.id not in task_ids:
                continue
            if python is None:
                python = mgr.ensure(family.new_env())
                from causal_data_juicer.sdk.schemas import digest_of
                env_freezes[family.name] = digest_of(
                    mgr.provenance(family.new_env()).get("frozen", []))
            tasks.append((task, python))
    task_by_id = {t.id: t for t, _ in tasks}

    fingerprint = env_fingerprint(registry, WORKLOAD_ID)
    fingerprint["agent_model"] = model
    fingerprint["fixer_model"] = fixer_model or model

    # 1) live collection
    episodes: list[Episode] = []
    snapshots: list[Snapshot] = []
    for task, python in tasks:
      for variant in range(max(1, episode_variants)):
        ws = run_dir / "workspaces" / (task.id if variant == 0 else f"{task.id}-v{variant}")
        task.setup(ws)
        write_env_pointer(ws, python)
        policy = LLMPolicy(llm, max_steps=max_steps)
        prompt = task.agent_prompt() + ("" if variant == 0
                                        else f"\n(independent attempt #{variant})") \
            + ((task_hints or {}).get(task.id, ""))
        policy.bind_task(prompt)
        episode, snaps = collector.run_episode(
            task.id, prompt, ws, policy,
            workload_id=WORKLOAD_ID, max_steps=max_steps,
        )
        violation = _seal_check(task, ws)
        if violation and episode.outcome and episode.outcome.success:
            episode.outcome.success = False
            episode.outcome.detail = f"[anti-cheat] {violation}"
        episode.meta.update({"family": task.family.name, "tier": task.tier,
                             "seal_violation": violation})
        episodes.append(episode)
        snapshots.extend(snaps)

    failures = [ep for ep in episodes if ep.outcome and not ep.outcome.success]

    # 2) fixer candidates (cached LLM), effect-signature dedup in screener
    screening_cost = CostLedger()
    source_objs = []
    for source_name in sources.split(","):
        if source_name == "fixer":
            source_objs.append(FixerLLMSource(
                fixer_llm, candidates_per_failure=fixer_candidates, ledger=screening_cost))
        elif source_name == "fixer-tests":
            source_objs.append(FixerLLMSource(
                fixer_llm, candidates_per_failure=fixer_candidates, ledger=screening_cost,
                name="fixer-tests",
                tests_by_task={tid: t.test_files() for tid, t in task_by_id.items()}))
        elif source_name == "resample":
            from causal_data_juicer.acquisition.resample import ResampleSource
            resample_llm = DiskCachedLLM(
                OpenAICompatClient(base_url, model, temperature=resample_temperature),
                cache_dir)
            source_objs.append(ResampleSource(resample_llm, k=resample_k,
                                              ledger=screening_cost))
        else:
            raise ValueError(f"unknown candidate source: {source_name}")
    screener = Screener(sources=source_objs)
    candidates = screener.screen(episodes)

    # 3) paired replay + repro + slicing (+ optional refinement loop)
    units: list[CausalUnit] = []
    control_cache: dict = {}

    def validate(ep, iv) -> CausalUnit:
        unit = replayer.paired_replay(ep, snapshots, iv, n_repro=n_repro,
                                      control_cache=control_cache)
        if unit.tier >= EvidenceTier.REPRODUCIBLE:
            unit = minimize_unit(replayer, ep, snapshots, unit)
        family = task_by_id[ep.task_id].family.name
        stamp(unit, {**fingerprint, "family": family,
                     f"env:{family}": env_freezes.get(family, "")})
        units.append(unit)
        return unit

    last_attempt: dict[str, tuple] = {}  # episode_id -> (iv, intervened detail)
    flipped_eps: set[str] = set()
    for ep, iv in candidates:
        unit = validate(ep, iv)
        if unit.flipped:
            flipped_eps.add(ep.id)
        elif unit.intervened_outcome is not None:
            last_attempt[ep.id] = (iv, unit.intervened_outcome.detail)

    if refine_rounds > 0:
        from causal_data_juicer.acquisition.fixer import propose_refinement
        eps_by_id = {ep.id: ep for ep in episodes}
        for ep_id, (iv, detail) in list(last_attempt.items()):
            if ep_id in flipped_eps:
                continue
            ep = eps_by_id[ep_id]
            tests = task_by_id[ep.task_id].test_files()
            for round_index in range(1, refine_rounds + 1):
                revised = propose_refinement(fixer_llm, ep, iv, detail, round_index,
                                             tests=tests, ledger=screening_cost)
                if revised is None:
                    break
                unit = validate(ep, revised)
                if unit.flipped:
                    flipped_eps.add(ep.id)
                    break
                if unit.intervened_outcome is None:
                    break
                iv, detail = revised, unit.intervened_outcome.detail

    exports = compile_all(units, episodes, run_dir / "exports")

    # 4) report with family/tier breakdown
    def bucket(unit: CausalUnit) -> tuple[str, int]:
        task = task_by_id[unit.task_id]
        return task.family.name, task.tier

    flipped = [u for u in units if u.flipped]
    repro_runs = sum(u.repro_runs for u in flipped)
    repro_flips = sum(u.repro_flips for u in flipped)
    total_cost = CostLedger()
    total_cost.merge(screening_cost)
    for ep in episodes:
        total_cost.merge(ep.cost)
    for u in units:
        total_cost.merge(u.cost)
    total_cost.wall_time_s = round(total_cost.wall_time_s, 2)
    validated = [u for u in units if u.tier >= EvidenceTier.COUNTERFACTUAL_VALIDATED]

    by_bucket: dict[str, dict] = {}
    for u in units:
        fam, tier = bucket(u)
        for key in (f"family:{fam}", f"tier:T{tier}"):
            b = by_bucket.setdefault(key, {"candidates": 0, "flipped": 0,
                                           "repro_flips": 0, "repro_runs": 0})
            b["candidates"] += 1
            b["flipped"] += int(u.flipped)
            b["repro_flips"] += u.repro_flips
            b["repro_runs"] += u.repro_runs

    match_vals = [u.control_digest_match for u in units if u.control_digest_match is not None]
    report = {
        "workload": WORKLOAD_ID,
        "agent_model": model,
        "episodes": len(episodes),
        "failed_episodes": len(failures),
        "agent_solved": len(episodes) - len(failures),
        "seal_violations": sum(1 for ep in episodes if ep.meta.get("seal_violation")),
        "candidates_screened": len(candidates),
        "units_by_tier": {
            tier.name: sum(1 for u in units if u.tier == tier)
            for tier in EvidenceTier if any(u.tier == tier for u in units)
        },
        "validated_units": len(validated),
        "flip_repro_rate": repro_flips / repro_runs if repro_runs else None,
        "flip_repro_detail": f"{repro_flips}/{repro_runs} intervened replays flipped",
        "determinism_control_ok": all(u.original_replay_match for u in units) if units else None,
        "control_digest_match_rate": (
            round(sum(match_vals) / len(match_vals), 4) if match_vals else None
        ),
        "breakdown": by_bucket,
        "slicing": {
            "atoms_before": sum(u.atoms_before_slicing for u in validated),
            "atoms_after": sum(u.atoms_after_slicing for u in validated),
        },
        "cost": total_cost.model_dump(),
        "cost_per_validated_unit_s": (
            round(sum(u.cost.wall_time_s for u in validated) / len(validated), 2)
            if validated else None
        ),
        "exports": {k: str(v) for k, v in exports.items()},
        "provenance": fingerprint,
        "wall_time_total_s": round(time.monotonic() - t_start, 2),
    }
    store.save(episodes, snapshots, units, report)
    shutil.rmtree(run_dir / "scratch", ignore_errors=True)
    return report
