"""`cdj migrate-run` — upgrade a run's snapshots to env-pointer v2.

Old snapshots recorded absolute interpreter paths; a directory rename or
a different machine breaks them. This rewrites every pointer inside the
run's content-addressed blobs to carry the env identity (name + pins),
recomputes tree digests, and updates snapshot/episode references —
observations and outcomes are untouched, so determinism digests and all
causal claims survive verbatim.
"""

from __future__ import annotations

import json
from pathlib import Path

from causal_data_juicer.run_store import RunStore
from causal_data_juicer.runtime.envs import ENV_POINTER, EnvManager
from causal_data_juicer.store.blob import tree_digest


def _env_identity(env_root: Path) -> dict[str, dict]:
    """name -> {python, pins} for every locally built env."""
    out = {}
    mgr = EnvManager(env_root)
    for marker in Path(mgr.root).glob("*/.causeforge_ready.json"):
        meta = json.loads(marker.read_text())
        out[meta["name"]] = {
            "python": str(marker.parent / "bin" / "python"),
            "pins": meta.get("requested", []),
        }
    return out


def migrate_run(run_dir: Path, env_root: Path = Path("bench_envs")) -> dict:
    store = RunStore(run_dir)
    envs = _env_identity(env_root)
    by_python_tail = {Path(v["python"]).parts[-3]: (k, v) for k, v in envs.items()}

    digest_map: dict[str, str] = {}
    rewritten = 0
    for tree in sorted(Path(store.blobs.root).iterdir()):
        pointer = tree / ENV_POINTER
        if not tree.is_dir() or not pointer.exists():
            continue
        data = json.loads(pointer.read_text())
        if "env_name" in data and Path(data["python"]).exists():
            continue  # already v2 and valid
        # match stale path to a local env by its directory name (e.g. 'pydantic-new')
        tail = Path(data["python"]).parts[-3] if len(Path(data["python"]).parts) >= 3 else None
        hit = by_python_tail.get(tail) if tail is not None else None
        if hit is None:
            continue
        name, info = hit
        data.update({"python": info["python"], "env_name": name, "pins": info["pins"]})
        pointer.write_text(json.dumps(data) + "\n")
        new_digest = tree_digest(tree)
        old_digest = tree.name
        if new_digest != old_digest:
            new_path = tree.parent / new_digest
            if not new_path.exists():
                tree.rename(new_path)
            digest_map[old_digest] = new_digest
            rewritten += 1

    episodes = store.load_episodes()
    snapshots = store.load_snapshots()
    units = store.load_units()
    for snap in snapshots:
        snap.tree_digest = digest_map.get(snap.tree_digest, snap.tree_digest)
    for ep in episodes:
        ep.final_tree_digest = digest_map.get(ep.final_tree_digest, ep.final_tree_digest)
    report = store.load_report() if (Path(run_dir) / "report.json").exists() else {}
    store.save(episodes, snapshots, units, report)
    return {"run": str(run_dir), "trees_rewritten": rewritten, "digests_remapped": len(digest_map)}
