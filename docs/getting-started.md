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
.venv/bin/python -m causal_data_juicer demo
```

Runs the full closed loop on a toy workload — collect, screen, paired
counterfactual replay, minimal slicing, four export views — and prints the
kill-line report (flip reproducibility, digest match, cost ledger).

```bash
.venv/bin/python -m causal_data_juicer regress runs/demo   # replay exported counterfactual cases
.venv/bin/python -m pytest tests/                  # 54 tests
```

## Commands

| Command | What it does |
|---|---|
| `causal_data_juicer demo` | end-to-end toy pipeline with kill-line report |
| `causal_data_juicer bench-build` | build + certify the 52-task migration bench (pass-old/fail-new) |
| `causal_data_juicer collect-depmig` | live LLM-agent collection; `--sources fixer,fixer-tests,resample`, `--refine-rounds N` |
| `causal_data_juicer acquire-eval` | matched-budget cost-per-unit curves across acquisition policies |
| `causal_data_juicer revalidate` | selective revalidation under a dependency version event |
| `causal_data_juicer storage-bench` | checkpoint-placement replay/storage trade-off |
| `causal_data_juicer export` | TRL-SFT / TRL-DPO / verl adapters |
| `causal_data_juicer import-trace` | Import Mode: observational ingestion of external traces |

## Live-agent collection

Point collection at any OpenAI-compatible endpoint (vLLM, commercial APIs):

```bash
causal_data_juicer collect-depmig \
  --base-url http://127.0.0.1:8010/v1 --model Qwen/Qwen2.5-7B-Instruct \
  --sources fixer-tests,resample --refine-rounds 3 --fixer-candidates 2
```

All LLM responses are disk-cached; replays never re-query a model.
