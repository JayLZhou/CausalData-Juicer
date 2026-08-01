# Replay pack: step-DPO case study

Proof by re-execution: this pack replays the full **live** step-DPO case
study — 19 failed agent episodes, 46 sampled counterfactual branches, 7
outcome flips, 12 same-state preference pairs — **byte-for-byte, with no
model and no network**. Every LLM response is served from the committed
cache; every branch outcome comes from really executing the replayed
workspace against its pinned environment.

```bash
# one-time: build the pinned task environments (needs network)
cdj bench-build

# replay (offline from here on)
mkdir -p /tmp/replay && cp -r replay-packs/step-dpo/llm_cache /tmp/replay/llm_cache
python examples/case_step_dpo.py --base replay-packs/step-dpo/base-run --out /tmp/replay
# expected: {"episodes": 19, "sampled_branches": 46,
#            "flipping_branches": 7, "step_dpo_pairs": 12}
```

Contents: `base-run/` (episodes, snapshots, content-addressed workspace
blobs with v2 env pointers) and `llm_cache/` (54 cached responses,
~220 KB). If an environment is missing, the pointer chain falls back
loudly — set `CDJ_BUILD_ENVS=1` to auto-build from the embedded pins.
A cache miss raises instead of silently querying a model: replays are
replays.
