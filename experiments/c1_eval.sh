#!/bin/bash
# C1 evaluation: base vs validated-LoRA vs suggested-LoRA agent solve
# rate on the held-out families (sqlalchemy + networkx, 16 tasks).
set -e
cd /home/jovyan/causeforge
HOLDOUT="s01_select_list s02_table_names s03_engine_execute s04_bind_autoload \
s05_session_raw_sql s06_autocommit k01_info k02_gpickle k03_ordered_graph \
k04_jit k05_persist_pipeline k06_report_tool k07_log_summary k08_jit_cache \
k09_ordered_store k10_dag_export"

echo "== launching eval server (GPU 1, :8013, base + 2 LoRA) =="
CUDA_VISIBLE_DEVICES=1 HF_HOME=/home/jovyan/buckets/hf_cache nohup \
  /home/jovyan/envs/graphrag/bin/vllm serve Qwen/Qwen2.5-7B-Instruct --port 8014 \
  --enable-lora --max-lora-rank 16 \
  --lora-modules validated=experiments/c1_adapters/validated \
                 suggested=experiments/c1_adapters/suggested \
  --gpu-memory-utilization 0.9 --max-model-len 8192 --disable-log-requests \
  > /home/jovyan/buckets/vllm_8013.log 2>&1 &
until curl -s http://127.0.0.1:8014/v1/models | grep -q validated; do sleep 5; done
echo "eval server ready"

for MODEL in Qwen/Qwen2.5-7B-Instruct validated suggested; do
  SAFE=$(echo "$MODEL" | tr '/' '_')
  echo "== arm: $MODEL =="
  .venv/bin/python -m causeforge collect-depmig \
    --out "runs/c1-eval-$SAFE" --base-url http://127.0.0.1:8014/v1 \
    --model "$MODEL" --fixer-candidates 0 \
    --tasks $HOLDOUT 2>&1 | grep -E "solved|FLIP" || true
done
echo "== summary =="
for SAFE in Qwen_Qwen2.5-7B-Instruct validated suggested; do
  .venv/bin/python - "$SAFE" <<'EOF'
import json, sys
run = f"runs/c1-eval-{sys.argv[1]}"
eps = [json.loads(l) for l in open(f"{run}/episodes.jsonl")]
ok = sum(1 for e in eps if e["outcome"]["success"])
print(f"{sys.argv[1]:<28} solved {ok}/{len(eps)}")
EOF
done
