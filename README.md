<div align="center">

# CauseForge

**A Budgeted Interventional Data Engine for Agent Improvement**

*One counterfactual execution machine. Any causal data-construction strategy in ~100 lines.*

[![CI](https://github.com/JayLZhou/CausalData-Juicer/actions/workflows/ci.yml/badge.svg)](https://github.com/JayLZhou/CausalData-Juicer/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-52%20passing-brightgreen.svg)](tests/)

[English] | [[中文](README_ZH.md)]

</div>

Experience systems store what agents *happened to try*;
**CauseForge actively acquires the causal experience agents *should learn from*.**

The engine forks a recorded trajectory at any step, applies an intervention,
replays original and intervened branches as a matched pair, verifies whether the
outcome actually **flips**, slices the intervention to its minimal causal core,
and compiles training-ready assets — with an explicit evidence tier on every row:

`Observed → Suggested → Counterfactual-Validated → Reproducible → Minimal → Training-Validated`

## 🔁 Reproduce a paper's data engine before lunch

The 2024–2026 branch-and-rollout family — MCTS→DPO pairs, tree credit
assignment, counterfactual ATE, process rewards, hindsight relabeling — all
hand-build the same loop: *branch → execute → compare → label*. CauseForge **is**
that loop as a library. Every reproduction below runs on the public API,
end-to-end, with real execution:

| Published strategy | Case study | Lines | Real output |
|---|---|---|---|
| MCTS → step-level DPO pairs | [`case_step_dpo.py`](examples/case_step_dpo.py) | 76 | 12 same-state preference pairs (live sampling + replay) |
| Rollout-tree credit (Tree-GRPO/RTMC) | [`case_rollout_tree.py`](examples/case_rollout_tree.py) | 78 | depth-2 executed trees, group-relative advantages |
| Counterfactual credit / ATE (CCPO) | [`case_credit_ate.py`](examples/case_credit_ate.py) | 53 | 9 credit-annotated trajectories, offline |
| Process-reward labels | (byproduct of `case_step_dpo.py`) | — | 46 executed-branch PRM labels |
| HER-style relabeling | [`case_her_relabel.py`](examples/case_her_relabel.py) | 43 | 34 achieved-goal rows, zero replay, zero LLM |
| **CAPER clause-level PRM** (arXiv:2606.03327, *June 2026*) | [`case_caper_clause_prm.py`](examples/case_caper_clause_prm.py) | 77 | clause criticality both directions — reproduced **same-day** |

Every case is a filling of one ten-line skeleton:

```python
episode, snapshots = collector.run_episode(task, workspace, policy)   # record
iv = Intervention(...)              # an alternative action, from any source:
                                    #   fixer LLM / temperature resample /
                                    #   test-aware prompt / clause perturbation
unit = replayer.paired_replay(episode, snapshots, iv)   # control + branch + n× repro
if unit.flipped:                    # outcome causally attributed, evidence-tiered
    export(unit)                    # -> SFT / DPO / PRM / memory / regression / verl / TRL
```

**Does your method fit?** Four questions: ① Does state fit in a snapshot
(filesystem + declared state)? ② Is there a swappable action? ③ Is execution
(near-)deterministic — a gate *rejects* flaky environments rather than emitting
false certificates? ④ Is there an automatic verifier? Four yeses ≈ a ~100-line
case study. (We reproduce papers' *data engines*, not their gradient updates —
outputs export straight into TRL/verl for that.)

## 📣 News

- **[2026-08-01]** CAPER (June 2026 paper) reproduced same-day in 77 lines — including the first **stress-direction** demo (pass→fail clause criticality): repair and stress are the same machinery with opposite sign.
- **[2026-08-01]** Every claims row now has a verdict: **A1–A14, B1–B5 lit; C1 recorded as an honest underpowered null** (validated ties unvalidated exactly at ~40 training rows; re-test conditions logged).
- **[2026-07-31]** Source science: coverage comes from *heterogeneous candidate sources* (blind/test-aware fixers × temperature resampling × validation-in-the-loop refinement) — the "capability ceiling" proved porous to cheap stochastic sources; failure→data conversion 24/35.
- **[2026-07-31]** Maintenance under two real version events: selective revalidation **4.8×/8.0×** cheaper, zero missed demotions. Checkpoint forking **298×** faster than from-scratch replay.
- **[2026-07-30]** Live-agent kill line: flip reproducibility **100%** with real LLM agents on the certified migration bench; control-branch digest match **100%**.

## ✨ What the engine gives every strategy for free

- 🔀 **Paired counterfactual replay** — a determinism control branch guards every claim; flips must reproduce n/n.
- 🧾 **Evidence tiers on every row** — weak evidence cannot masquerade as causal; ceilings are enforced (Import Mode caps at OBSERVED).
- 💰 **Budget layer** — token/second/dollar ledgers from line one; control-branch memoization and early stopping (26% replay savings measured); pluggable acquisition policies metered on equal ground.
- 🛡️ **Side-effect gating** — tools declare `PURE … EXTERNAL_SIDE_EFFECT`; external effects are never re-executed during replay.
- 🧬 **Provenance & freshness** — per-dependency claims per unit; version events trigger selective revalidation with demotion on staleness.
- 🧪 **A certified workload** — 52 dependency-migration tasks across 6 families, each certified pass-on-old / fail-on-new, hermetic, sealed, anti-cheat verified.

## 🚀 Quick Start

```bash
git clone https://github.com/JayLZhou/CausalData-Juicer.git && cd CausalData-Juicer
python3 -m venv .venv && .venv/bin/pip install -e .

.venv/bin/python -m causeforge demo              # end-to-end loop, one command
.venv/bin/python -m causeforge regress runs/demo # replay exported counterfactual cases
.venv/bin/python -m pytest tests/
```

| Command | What it does |
|---|---|
| `demo` / `bench-build` | toy loop with kill-line report / certify the 52-task bench |
| `collect-depmig` | live agent collection; `--sources fixer,fixer-tests,resample`, `--refine-rounds N` |
| `acquire-eval` / `storage-bench` | budgeted policy curves / checkpoint placement trade-off |
| `revalidate` | selective revalidation under a dependency version event |
| `export` / `import-trace` | TRL-SFT / TRL-DPO / verl adapters / observational Import Mode |

## 📊 Measured results

Every number is wired to an experiment and a pre-registered threshold in
[experiments/claims.md](experiments/claims.md) (raw reports in
[experiments/results/](experiments/results/)) — including the honest nulls.

| Claim | Result |
|---|---|
| Flip reproducibility (kill line ≥90%) | **100% across 11 configurations** (toy → live agents → cross-interpreter) |
| Control-branch digest match | **100%**, with CI-enforced negative controls (flaky envs get rejected) |
| Mechanism-layer savings | **26%** fewer replays, identical output |
| Budgeted acquisition (295 candidates) | adaptive leads at tight budgets (+33% @30 replays), converges when budget abounds |
| Selective revalidation (2 real events) | **4.8× / 8.0×** cheaper, zero missed demotions |
| Checkpoint forking | **298×** vs from-scratch; byte-identical state reconstruction |
| Source-fidelity science | conversion 24/35; stochastic sources pierce the deterministic-model ceiling |
| Training value (C1) | honest **underpowered null** at ~40 rows; re-test conditions logged |

## 🎚️ Access tiers

| Tier | You provide | Operators | Evidence ceiling |
|---|---|---|---|
| Import Mode | traces (JSONL) | observational + compile | OBSERVED |
| Tool Replay | tools + verifier | + local interventions | COUNTERFACTUAL-VALIDATED |
| Snapshot Mode | replayable env | everything | MINIMAL+ |

## 📚 Documentation

- [Design document](docs/design.md) · [Bench spec](docs/bench-m15-spec.md) · [Claims ledger](experiments/claims.md) · [中文项目合同](README_ZH.md)

## ⚖️ License & Citation

Apache-2.0.

```bibtex
@misc{causeforge2026,
  title  = {CauseForge: A Budgeted Interventional Data Engine for Agent Improvement},
  author = {Zhou, Yingli},
  year   = {2026},
  url    = {https://github.com/JayLZhou/CausalData-Juicer}
}
```

The name nods to [Data-Juicer](https://github.com/modelscope/data-juicer):
they refine the data you already have; we run the executions that create the
data you're missing — the interventional axis, upstream of the observational one.
