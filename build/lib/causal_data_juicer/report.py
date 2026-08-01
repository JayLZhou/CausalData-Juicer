"""`cdj explain` — the result page.

A run is not a pile of JSONL: for each causal unit, say in plain language
which step went wrong, what changed (as a diff), why it counts as causal
(control matched, flip reproduced), its evidence tier, and its cost.
Terminal cards plus an optional self-contained static HTML report.
"""
from __future__ import annotations

import difflib
import html as html_mod
from pathlib import Path

from causal_data_juicer.run_store import RunStore
from causal_data_juicer.sdk.schemas import CausalUnit, Episode, EvidenceTier


def _changed(episode: Episode, unit: CausalUnit) -> tuple[str, list[str]]:
    from causal_data_juicer.interventions.apply import apply_intervention
    iv = unit.effective_intervention()
    original = episode.steps[iv.target_step].action
    corrected = apply_intervention(original, iv)
    o = str(original.args.get("content", original.args))
    c = str(corrected.args.get("content", corrected.args))
    diff = list(difflib.unified_diff(o.splitlines(), c.splitlines(),
                                     "agent wrote", "validated fix", lineterm="", n=1))
    return str(corrected.args.get("path", original.tool)), diff


def unit_card(unit: CausalUnit, episode: Episode, exports_dir: Path) -> str:
    iv = unit.effective_intervention()
    path, diff = _changed(episode, unit)
    o = unit.original_outcome
    lines = [
        f"Task              : {unit.task_id} — {episode.task_description.splitlines()[0][:80]}",
        f"Original outcome  : FAIL ({o.passed} passed, {o.failed} failed)",
        f"Intervention      : {iv.type.value} @ step {iv.target_step} on {path}"
        f"  (source: {iv.source or 'n/a'})",
        f"Control replay    : {'MATCHED' if unit.original_replay_match else 'MISMATCH — unit refused'}",
    ]
    if unit.flipped:
        lines += [
            "Intervened outcome: PASS",
            f"Reproduction      : {unit.repro_flips}/{unit.repro_runs}",
            f"Minimal edit      : {unit.atoms_after_slicing or unit.atoms_before_slicing} atom(s)"
            + (f" (sliced from {unit.atoms_before_slicing})"
               if unit.atoms_after_slicing and unit.atoms_after_slicing < unit.atoms_before_slicing else ""),
        ]
    else:
        lines += ["Intervened outcome: still failing — candidate rejected"]
    lines += [
        f"Evidence          : {unit.tier.name}",
        f"Cost              : {unit.cost.replay_runs} replays / {unit.cost.wall_time_s:.1f}s"
        f" / ${unit.cost.dollars:.4f}",
        f"Exports           : {exports_dir}/(sft|dpo|memory|regression).jsonl",
    ]
    if diff:
        lines += ["What changed      :"] + [f"    {d}" for d in diff[:16]]
    return "\n".join(lines)


def explain_text(run_dir: Path, include_rejected: bool = False) -> str:
    store = RunStore(run_dir)
    episodes = {ep.id: ep for ep in store.load_episodes()}
    units = store.load_units()
    keep = [u for u in units
            if u.tier >= EvidenceTier.COUNTERFACTUAL_VALIDATED or include_rejected]
    out = [f"# {run_dir} — {len(keep)} unit(s)"]
    for u in keep:
        out.append("─" * 66)
        out.append(unit_card(u, episodes[u.episode_id], Path(run_dir) / "exports"))
    return "\n".join(out)


_HTML_HEAD = """<!doctype html><meta charset="utf-8">
<title>CausalData-Juicer report</title><style>
body{font:14px/1.5 -apple-system,Segoe UI,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#222}
.card{border:1px solid #ddd;border-radius:10px;padding:1rem 1.2rem;margin:1rem 0;box-shadow:0 1px 3px #0001}
.tier{display:inline-block;padding:.1rem .55rem;border-radius:999px;color:#fff;font-weight:600;font-size:12px}
.MINIMAL,.REPRODUCIBLE{background:#2e7d32}.COUNTERFACTUAL_VALIDATED{background:#f9a825}
.SUGGESTED{background:#9e9e9e}
pre{background:#f6f8fa;border-radius:6px;padding:.7rem;overflow-x:auto;font-size:12.5px}
.del{color:#b31d28;background:#ffeef0}.add{color:#22863a;background:#e6ffed}
dt{font-weight:600;float:left;width:11.5rem}dd{margin:0 0 .15rem 12rem}
h1{font-size:1.35rem}</style>
"""


def explain_html(run_dir: Path, out_file: Path) -> Path:
    store = RunStore(run_dir)
    episodes = {ep.id: ep for ep in store.load_episodes()}
    units = [u for u in store.load_units()
             if u.tier >= EvidenceTier.COUNTERFACTUAL_VALIDATED]
    parts = [_HTML_HEAD, f"<h1>CausalData-Juicer — {html_mod.escape(str(run_dir))} "
                         f"({len(units)} validated units)</h1>"]
    for u in units:
        ep = episodes[u.episode_id]
        iv = u.effective_intervention()
        path, diff = _changed(ep, u)
        e = html_mod.escape
        rows = [
            ("Task", f"{u.task_id} — {ep.task_description.splitlines()[0][:90]}"),
            ("Original outcome", f"FAIL ({u.original_outcome.passed} passed, "
                                 f"{u.original_outcome.failed} failed)"),
            ("Intervention", f"{iv.type.value} @ step {iv.target_step} on {path} "
                             f"(source: {iv.source or 'n/a'})"),
            ("Control replay", "MATCHED" if u.original_replay_match else "MISMATCH"),
            ("Intervened outcome", "PASS" if u.flipped else "still failing"),
            ("Reproduction", f"{u.repro_flips}/{u.repro_runs}"),
            ("Cost", f"{u.cost.replay_runs} replays / {u.cost.wall_time_s:.1f}s"),
        ]
        dl = "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in rows)
        diff_html = "".join(
            f'<span class="{"del" if d.startswith("-") else "add" if d.startswith("+") else ""}">'
            f"{e(d)}</span>\n" for d in diff[:40])
        parts.append(
            f'<div class="card"><span class="tier {u.tier.name}">{u.tier.name}</span>'
            f"<dl>{dl}</dl><pre>{diff_html}</pre></div>")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("".join(parts))
    return out_file
