# Integrations

## TRL (SFT / DPO)

```bash
cdj export --run runs/my-run --format trl-dpo   # {prompt, chosen, rejected}
cdj export --run runs/my-run --format trl-sft   # {messages: [...]}
```

```python
from datasets import load_dataset
from trl import DPOConfig, DPOTrainer

dataset = load_dataset("json", data_files="runs/my-run/exports/trl-dpo.jsonl")["train"]
trainer = DPOTrainer(model, args=DPOConfig(...), train_dataset=dataset,
                     processing_class=tokenizer)
```

Extra columns (`evidence_tier`, `unit_id`) ride along for filtering —
e.g. `dataset.filter(lambda r: r["evidence_tier"] == "MINIMAL")`.

## verl

```bash
cdj export --run runs/my-run --format verl      # parquet, nested structs native
```

Rows follow verl's RLHF dataset shape: `prompt` (chat messages),
`data_source`, `reward_model` (`{"style": "rule", "ground_truth": ...}`),
`extra_info`. Point your verl config's data path at the parquet file.

## Data-Juicer

Our exports are plain JSONL/parquet — feed them to DJ pipelines as an
upstream, high-confidence source; or express your DJ-style recipe directly
here (`cdj process --config recipe.yaml`) when steps need real execution.

## Your agent framework (Import Mode)

Dump traces as JSONL — five fields, nothing else:

```json
{"task_id": "t1", "description": "...", "success": false,
 "steps": [{"tool": "write_file", "args": {...}, "observation": "..."}]}
```

`cdj import-trace traces.jsonl` ingests them with the OBSERVED evidence
ceiling enforced. Framework-specific adapters (SWE-agent, OpenHands) are on
the roadmap — contributions welcome, the target schema is above.
