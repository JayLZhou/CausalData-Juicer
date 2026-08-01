# Troubleshooting

Start with `cdj doctor --base-url <your endpoint>` — it checks Python,
dependencies, scratch space and endpoint reachability with hints.

**`pytest: command not found` (or any bare command) in `--verify`.**
Handled automatically: if the executable isn't on PATH, we run
`<workspace-python> -m <cmd>` instead. If your check truly isn't a Python
module, give an absolute path or use `{python}` expansion:
`--verify "{python} scripts/check.py"`.

**The agent produces zero steps with a reasoning model (Qwen3 etc.).**
`<think>` blocks are stripped (including truncated ones) and repo context is
injected into the prompt so the model acts instead of deliberating blind.
If you still see empty episodes, raise the endpoint's `max_tokens`.

**`env pointer ... is stale` warning during replay.**
The run was recorded on another machine or the repo moved. Run
`cdj migrate-run <run_dir>` to upgrade pointers to v2 (env identity), or
`cdj bench-build` to create local envs the pointer chain can find, or set
`CDJ_BUILD_ENVS=1` to auto-build from the pins embedded in the pointer.

**Replay pack numbers don't match the README.**
First `cdj bench-build` (the pack executes real environments). A cache miss
raises rather than silently querying a model — if you see a connection
error, the `llm_cache/` directory wasn't copied next to your `--out` dir.

**`already passes — nothing to fix` from `cdj run`.**
Your verifier passes on the baseline. Point `--verify` at the failing
check, or wait for the stress direction (pass→fail perturbation) if you
wanted robustness probing.

**Everything is SUGGESTED, nothing validates.**
Read one unit with `cdj explain <run> --all`: if `Control replay: MISMATCH`,
your environment is nondeterministic at outcome level (hidden state, time,
network) — fix the workload, not the engine. If control matches but nothing
flips, your candidates are just wrong; add sources
(`--sources fixer-tests,resample --refine-rounds 3`) or a stronger fixer.

**vLLM + AWQ models:** use `--quantization awq_marlin` on A100s; reasoning
models may need larger `--max-model-len` for repo-context prompts.
