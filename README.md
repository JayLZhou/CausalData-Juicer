<div align="center">

# CauseForge

**A Budgeted Interventional Data Engine for Agent Improvement**

[![CI](https://github.com/JayLZhou/CausalData-Juicer/actions/workflows/ci.yml/badge.svg)](https://github.com/JayLZhou/CausalData-Juicer/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-52%20passing-brightgreen.svg)](tests/)

[English] | [[中文](README_ZH.md)]

</div>

Experience systems store what agents *happened to try*;
**CauseForge actively acquires the causal experience agents *should learn from*.**
The engine decides which trajectory states to fork, applies interventions, replays
original and intervened branches as a matched pair, verifies whether the outcome
actually flips, slices interventions to their minimal causal core, and compiles
training-ready assets — with an explicit **evidence tier on every row**:

`Observed → Suggested → Counterfactual-Validated → Reproducible → Minimal → Training-Validated`

If you know [Data-Juicer](https://github.com/modelscope/data-juicer): Data-Juicer
refines the data you already have; CauseForge decides **which executions to run**
to create the data you're missing — and proves each unit changed the outcome.
Operators extend the observational algebra with an interventional signature:
`(Units, Env, Budget) → Units'`.

## 📣 News

- **[2026-07-31]** Experiment program closed out: claims **A1–A14 + B1/B2 all lit**; corpus 59 validated units over the 52-task bench; flip reproducibility **100% in 11 configurations**.
- **[2026-07-31]** Source-fidelity ladder (A12): blind fixer → resampling → test-aware fixer → validation-in-the-loop refinement; the "capability ceiling" proved porous to cheap stochastic sources.
- **[2026-07-31]** Selective revalidation under two real version events: **4.8× / 8.0×** fewer replays, zero missed demotions (A8). Checkpoint forking **298×** faster than from-scratch replay (A6).
- **[2026-07-30]** Live-agent jackpot: flip reproducibility **100% (15/15)** with a real LLM agent on the certified 30-task migration bench; control-branch digest match **100%** (A9 — a number nobody else reports).
- **[2026-07-29]** M1 vertical slice end-to-end; kill lines baked into CI.

## 📖 Table of Contents

- [Features](#-features)
- [Quick Start](#-quick-start)
- [Commands](#-commands)
- [Measured Results](#-measured-results)
- [Access Tiers](#-access-tiers)
- [Documentation](#-documentation)
- [License & Citation](#-license--citation)

## ✨ Features

- 🔀 **Paired counterfactual replay** — every candidate fix is validated against a
  determinism control branch forked from the same snapshot; only outcome flips
  that reproduce n/n become data.
- 🧾 **Evidence tiers everywhere** — weak evidence can never masquerade as causal;
  every API surface and every exported row carries its tier.
- 💰 **Budget layer** — cost ledgers from line one (tokens/seconds/dollars);
  always-on mechanisms (control memoization, early stopping, full LLM response
  caching) plus pluggable acquisition policies competing on metered ground.
- 🛡️ **Side-effect–graded execution** — tools declare `PURE … EXTERNAL_SIDE_EFFECT`;
  external effects are never truly re-executed during replay (dry-run mock only).
- 🧬 **Provenance & freshness** — per-dependency claims on every unit; version
  events trigger *selective* revalidation with demotion on staleness.
- 🧪 **Certified workload** — a 52-task dependency-migration bench (6 families),
  every task certified pass-on-old / fail-on-new pins, hermetic and sealed.
- 📦 **Training-stack exports** — TRL SFT/DPO, verl parquet, plus agent-memory and
  executable counterfactual regression suites.
- 🔌 **Import Mode** — ingest external traces (JSONL) with observational operators
  only; the evidence ceiling (OBSERVED) is enforced, not implied.

## 🚀 Quick Start

```bash
git clone https://github.com/JayLZhou/CausalData-Juicer.git && cd CausalData-Juicer
python3 -m venv .venv && .venv/bin/pip install -e .

# one-command end-to-end demo (collect -> screen -> paired replay -> slice -> compile)
.venv/bin/python -m causeforge demo

# replay the exported counterfactual regression suite
.venv/bin/python -m causeforge regress runs/demo

.venv/bin/python -m pytest tests/
```

## 🛠️ Commands

| Command | What it does |
|---|---|
| `causeforge demo` | end-to-end toy pipeline with kill-line report |
| `causeforge bench-build` | build + certify the migration bench (pass-old/fail-new) |
| `causeforge collect-depmig` | live LLM-agent collection; `--sources fixer,fixer-tests,resample`, `--refine-rounds N` |
| `causeforge acquire-eval` | matched-budget cost-per-unit curves across acquisition policies |
| `causeforge revalidate` | selective revalidation under a dependency version event |
| `causeforge storage-bench` | checkpoint-placement replay/storage trade-off |
| `causeforge export` | TRL-SFT / TRL-DPO / verl adapters |
| `causeforge import-trace` | Import Mode: observational ingestion of external traces |

## 📊 Measured Results

All numbers wired to experiments and thresholds in
[experiments/claims.md](experiments/claims.md); raw reports in
[experiments/results/](experiments/results/).

| Claim | Result |
|---|---|
| Flip reproducibility (kill line ≥ 90%) | **100% in 11 configurations**, toy → live LLM agents → cross-interpreter |
| Control-branch digest match | **100%**, with CI-enforced negative controls (outcome-flaky envs are rejected) |
| Mechanism-layer savings | **26%** fewer replays at identical output |
| Budgeted acquisition (295-candidate pool) | adaptive policy leads at tight budgets (+33% @30 replays), converges when budget abounds |
| Selective revalidation (2 real version events) | **4.8× / 8.0×** fewer replays, zero missed demotions |
| Checkpoint forking | **298×** faster than from-scratch replay; byte-identical state reconstruction |
| Source-fidelity ladder | failure→data conversion **24/35**; stochastic sources pierce the deterministic-model ceiling |
| Expressiveness | step-DPO pipeline in **76 lines**, counterfactual credit (ATE) in **53 lines**, on the public API |

## 🎚️ Access Tiers

| Tier | You provide | Operators | Evidence ceiling |
|---|---|---|---|
| Import Mode | traces (JSONL) | observational + compile | OBSERVED |
| Tool Replay | tools + verifier | + local interventions | COUNTERFACTUAL-VALIDATED |
| Snapshot Mode | replayable env | everything | MINIMAL+ |

## 📚 Documentation

- [Design document](docs/design.md) — abstractions, closed loop, evidence ladder
- [Migration bench spec](docs/bench-m15-spec.md) — task shapes, hermeticity, verifier contract
- [Claims ledger](experiments/claims.md) — every claim → experiment → threshold → status
- [中文项目合同](README_ZH.md) — roadmap, kill lines, scope discipline

## ⚖️ License & Citation

Apache-2.0. If you use CauseForge in your research:

```bibtex
@misc{causeforge2026,
  title  = {CauseForge: A Budgeted Interventional Data Engine for Agent Improvement},
  author = {Zhou, Yingli},
  year   = {2026},
  url    = {https://github.com/JayLZhou/CausalData-Juicer}
}
```

Positioning homage: the name nods to
[Data-Juicer](https://github.com/modelscope/data-juicer) — we sit upstream of
observational data processing, on the interventional axis.
