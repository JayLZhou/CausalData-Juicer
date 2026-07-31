# Getting started

## Install

```bash
git clone https://github.com/JayLZhou/CausalData-Juicer.git && cd CausalData-Juicer
python3 -m venv .venv && .venv/bin/pip install -e .
```

Python 3.11+ · dependencies: pydantic, pytest (pyarrow optional, for verl
parquet export).

## Two-minute demo

```bash
.venv/bin/python -m causeforge demo
```

Runs the full closed loop on a toy workload — collect, screen, paired
counterfactual replay, minimal slicing, four export views — and prints the
kill-line report (flip reproducibility, digest match, cost ledger).

```bash
.venv/bin/python -m causeforge regress runs/demo   # replay exported counterfactual cases
.venv/bin/python -m pytest tests/                  # 54 tests
```

## Commands

| Command | What it does |
|---|---|
| `causeforge demo` | end-to-end toy pipeline with kill-line report |
| `causeforge bench-build` | build + certify the 52-task migration bench (pass-old/fail-new) |
| `causeforge collect-depmig` | live LLM-agent collection; `--sources fixer,fixer-tests,resample`, `--refine-rounds N` |
| `causeforge acquire-eval` | matched-budget cost-per-unit curves across acquisition policies |
| `causeforge revalidate` | selective revalidation under a dependency version event |
| `causeforge storage-bench` | checkpoint-placement replay/storage trade-off |
| `causeforge export` | TRL-SFT / TRL-DPO / verl adapters |
| `causeforge import-trace` | Import Mode: observational ingestion of external traces |

## Live-agent collection

Point collection at any OpenAI-compatible endpoint (vLLM, commercial APIs):

```bash
causeforge collect-depmig \
  --base-url http://127.0.0.1:8010/v1 --model Qwen/Qwen2.5-7B-Instruct \
  --sources fixer-tests,resample --refine-rounds 3 --fixer-candidates 2
```

All LLM responses are disk-cached; replays never re-query a model.
