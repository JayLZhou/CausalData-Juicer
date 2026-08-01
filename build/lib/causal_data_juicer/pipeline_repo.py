"""`cdj run` — the bring-your-own-repo entry point.

    cdj run --repo ./my-project --verify "pytest -q" --base-url http://...

Copies the repo into a workspace, checks the verifier actually fails,
lets a live agent attempt the task, mines candidate fixes from the
heterogeneous source pool, validates them with paired counterfactual
replay, and ends with a human-readable report (terminal + HTML) plus
the four export views. One command from "my tests fail" to "here are
certified correction pairs".
"""
from __future__ import annotations

import shlex
import shutil
import time
from pathlib import Path

from causal_data_juicer.acquisition.fixer import FixerLLMSource
from causal_data_juicer.acquisition.resample import ResampleSource
from causal_data_juicer.acquisition.screener import Screener
from causal_data_juicer.compiler.exports import compile_all
from causal_data_juicer.maintenance.provenance import env_fingerprint, stamp
from causal_data_juicer.replay.replayer import Replayer
from causal_data_juicer.replay.sandbox import LocalSandbox
from causal_data_juicer.runtime.collector import Collector
from causal_data_juicer.runtime.llm import DiskCachedLLM, OpenAICompatClient
from causal_data_juicer.runtime.llm_policy import LLMPolicy
from causal_data_juicer.runtime.tools import (
    SideEffectClass,
    Tool,
    ToolRegistry,
    _read_file,
    _write_file,
)
from causal_data_juicer.runtime.verifier import CommandVerifier
from causal_data_juicer.run_store import RunStore
from causal_data_juicer.sdk.schemas import CausalUnit, CostLedger, EvidenceTier
from causal_data_juicer.slicing.ddmin import minimize_unit

EXCLUDE = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".tox"}

REPO_SYSTEM_PROMPT = """\
You are a coding agent working inside an isolated copy of a repository.
Available tools (respond with EXACTLY one JSON object, nothing else):
  {"tool": "read_file",  "args": {"path": "<relative path>"}}
  {"tool": "write_file", "args": {"path": "<relative path>", "content": "<full file content>"}}
  {"tool": "run_check",  "args": {}}
  {"tool": "done",       "args": {}}
Rules: always write complete file contents; run the check after editing;
reply {"tool": "done", "args": {}} once the check passes or you cannot progress."""


def _repo_context(ws: Path, max_file: int = 4000, max_total: int = 9000) -> str:
    """Inline small file contents so the agent (and its fixer) start with
    eyes open instead of spelunking — crucial for reasoning models."""
    parts, total = [], 0
    for p in sorted(ws.rglob("*")):
        if not p.is_file() or any(seg in EXCLUDE for seg in p.parts):
            continue
        try:
            txt = p.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if len(txt) > max_file:
            continue
        chunk = f"\n--- {p.relative_to(ws)} ---\n{txt}"
        if total + len(chunk) > max_total:
            break
        parts.append(chunk)
        total += len(chunk)
    return "".join(parts)


def _copy_repo(repo: Path, dest: Path) -> None:
    def ignore(_dir, names):
        return [n for n in names if n in EXCLUDE]
    shutil.copytree(repo, dest, ignore=ignore)


def _registry_for(verify_argv: list[str], sealed=None) -> ToolRegistry:
    import subprocess

    def run_check(workspace: Path) -> str:
        from causal_data_juicer.runtime.verifier import resolve_command
        if sealed is not None:
            sealed.restore(workspace)  # the in-episode check is sealed too
        proc = subprocess.run(resolve_command(verify_argv, workspace), cwd=workspace,
                              capture_output=True, text=True, timeout=300)
        tail = (proc.stdout + proc.stderr).strip()[-4000:]
        return f"{tail}\n[exit={proc.returncode}]"

    reg = ToolRegistry()
    reg.register(Tool("write_file", SideEffectClass.REVERSIBLE, _write_file))
    reg.register(Tool("read_file", SideEffectClass.PURE, _read_file))
    reg.register(Tool("run_check", SideEffectClass.IDEMPOTENT, run_check,
                      normalize=lambda obs: obs.rsplit("[", 1)[-1].rstrip("]\n")))
    return reg


def _remine_success(episode, snapshots, repo, out, collector, replayer):
    """The agent succeeded: re-record the same trajectory with the fixing
    write replaced by an identity write (a genuinely failing control
    episode), then propose the agent's real fix as the intervention.
    Success thus also yields certified correction pairs."""
    from causal_data_juicer.acquisition.fixer import last_write_step
    from causal_data_juicer.runtime.agent import ScriptedPolicy, ScriptedStep
    from causal_data_juicer.sdk.schemas import Intervention, InterventionType

    k = last_write_step(episode)
    if k is None:
        return episode, snapshots, []
    fix_action = episode.steps[k].action
    snap = next(s for s in snapshots
                if s.episode_id == episode.id and s.step_index == k)
    pre = replayer.sandbox.materialize(snap.tree_digest)
    try:
        original = (pre / fix_action.args["path"]).read_text() \
            if (pre / fix_action.args["path"]).exists() else ""
    finally:
        replayer.sandbox.dispose(pre)

    identity = fix_action.model_copy(deep=True)
    identity.args = {**fix_action.args, "content": original}
    script = [ScriptedStep(action=(identity if st.index == k else st.action))
              for st in episode.steps]
    ws2 = out / "workspaces" / f"{repo.name}-control"
    _copy_repo(repo, ws2)
    ep2, snaps2 = collector.run_episode(
        repo.name, episode.task_description, ws2,
        ScriptedPolicy(script), workload_id="byo-repo")
    if ep2.outcome.success:      # identity control unexpectedly passes: bail
        return episode, snapshots, []
    iv = Intervention(type=InterventionType.ACTION_REPLACE, target_step=k,
                      new_action=fix_action, rationale="the agent's own successful fix",
                      source="agent-self")
    return ep2, snaps2, [(ep2, iv)]


def run_repo(
    repo: Path,
    verify: str,
    base_url: str,
    model: str,
    out: Path,
    task: str | None = None,
    n_repro: int = 3,
    max_steps: int = 10,
    fixer_candidates: int = 2,
    resample_k: int = 2,
) -> dict:
    t0 = time.monotonic()
    repo = Path(repo).resolve()
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    store = RunStore(out)
    verify_argv = shlex.split(verify)

    ws = out / "workspaces" / repo.name
    _copy_repo(repo, ws)

    from causal_data_juicer.runtime.verifier import SealedVerifier
    verifier = SealedVerifier(CommandVerifier(verify_argv, timeout=300), ws)
    registry = _registry_for(verify_argv, sealed=verifier)
    collector = Collector(registry, store.blobs, verifier)
    replayer = Replayer(registry, LocalSandbox(store.blobs, out / "scratch"), verifier)

    baseline = verifier.evaluate(ws, CostLedger())
    if baseline.success:
        print(f"`{verify}` already passes in {repo} — nothing to fix. "
              f"(Stress direction is on the roadmap.)")
        return {"status": "already-passing"}
    print(f"baseline: `{verify}` fails — collecting an agent attempt…")

    llm = DiskCachedLLM(OpenAICompatClient(base_url, model, max_tokens=4096),
                    out / "llm_cache")
    description = task or (
        f"Make the check `{verify}` pass in this repository. Current failure:\n"
        + "\n".join(baseline.detail.splitlines()[-12:])
        + "\n\nRepository files:" + _repo_context(ws))
    system_prompt = REPO_SYSTEM_PROMPT
    if "qwen3" in model.lower():
        system_prompt += " /no_think"
    policy = LLMPolicy(llm, max_steps=max_steps, system_prompt=system_prompt)
    policy.bind_task(description)
    episode, snapshots = collector.run_episode(repo.name, description, ws, policy,
                                               workload_id="byo-repo", max_steps=max_steps)
    if episode.outcome.success:
        print("the agent fixed it — certifying its own fix as a causal unit…")
        episode, snapshots, mined = _remine_success(
            episode, snapshots, repo, out, collector, replayer)
        candidates_extra = mined
    else:
        candidates_extra = []
    screening_cost = CostLedger()
    screener = Screener(sources=[
        FixerLLMSource(llm, candidates_per_failure=fixer_candidates, ledger=screening_cost),
        ResampleSource(DiskCachedLLM(OpenAICompatClient(base_url, model, temperature=0.85, max_tokens=4096),
                                     out / "llm_cache"), k=resample_k, ledger=screening_cost),
    ])
    candidates = candidates_extra + screener.screen([episode])
    print(f"screened {len(candidates)} candidate fixes — validating with paired replay…")

    units: list[CausalUnit] = []
    control_cache: dict = {}
    fingerprint = env_fingerprint(registry, "byo-repo")
    fingerprint["verify"] = verify
    for ep, iv in candidates:
        unit = replayer.paired_replay(ep, snapshots, iv, n_repro=n_repro,
                                      control_cache=control_cache, early_stop_repro=True)
        if unit.tier >= EvidenceTier.REPRODUCIBLE:
            unit = minimize_unit(replayer, ep, snapshots, unit)
        stamp(unit, fingerprint)
        units.append(unit)

    exports = compile_all(units, [episode], out / "exports")
    validated = [u for u in units if u.tier >= EvidenceTier.COUNTERFACTUAL_VALIDATED]
    total = CostLedger()
    total.merge(screening_cost)
    total.merge(episode.cost)
    for u in units:
        total.merge(u.cost)
    report = {
        "status": "ok", "repo": str(repo), "verify": verify,
        "agent_solved": episode.outcome.success,
        "candidates": len(candidates), "validated_units": len(validated),
        "seal_violations": verifier.violations,
        "cost": total.model_dump(),
        "exports": {k: str(v) for k, v in exports.items()},
        "wall_time_s": round(time.monotonic() - t0, 1),
    }
    store.save([episode], snapshots, units, report)
    shutil.rmtree(out / "scratch", ignore_errors=True)
    return report
