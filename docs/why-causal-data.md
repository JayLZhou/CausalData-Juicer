# Why causal data

**Causal data** for LLM/agent training is data whose labels answer an
*interventional* question — **"would the outcome have changed under a
different action?"** — not the observational one ("what happened?"). Each
counterfactual is one controlled comparison: fork the state, swap one thing,
execute, diff the outcomes. It is the only way to get credit assignment
without guessing, preference pairs that aren't stylistic, and process labels
grounded in execution — which is why everyone is building it now:

| You want | The counterfactual question | Representative methods | Data produced |
|---|---|---|---|
| Step-level credit in reasoning | would the solution still succeed if *this* step changed? | MCTS→step-DPO, PRM construction | step-DPO pairs, PRM labels |
| Advantage signals for agent RL | how much better is this branch than its siblings from the same state? | TreeRL, Tree-GRPO, ARPO; CCPO, RTMC, AT2PO | group advantages, per-step credit |
| Repair data for code agents | does this patch actually flip the failing test? | patch–outcome mining (our bench domain) | validated correction / DPO pairs |
| Process supervision for structured generation | which clause breaks or repairs execution? | CAPER (Text-to-SQL) | clause-level PRM labels |
| Supervision recycled from failures | what goal did this failure *actually* achieve? | HER-style relabeling | hindsight SFT rows |
| Credit & blame in multi-agent systems | which agent's message, if changed, would have flipped the team outcome? | COMA-lineage counterfactual baselines; LLM-MAS failure attribution & message-credit ablations | per-agent / per-message credit, blame labels |
| Skill & memory libraries | does this recovery, replayed from the failure state, actually flip it — and does it transfer? | failure→recovery mining; skill libraries with counterfactual validation | validated skills, failure→recovery units |
| Robustness & regression labels | what is the smallest perturbation that breaks a success? | stress testing (v2 here) | criticality labels, adversarial suites |

*(Every row above is backed by 3–7 verified papers — venues, arXiv and code links — in [docs/landscape-papers.md](landscape-papers.md).)*

Strip away the rows and one act remains: **fork a state, run an alternative,
compare outcomes, keep the difference.**

## Versus observational data processing

| | Data-Juicer family | **CausalData-Juicer** |
|---|---|---|
| Input | corpora you already have | a replayable execution environment |
| Core act | operator transforms (filter/dedup/synthesize) | fork / intervene / paired counterfactual replay |
| Quality signal | heuristics & model scores (pool-level, observational) | verifier outcome **flips** (unit-level, interventional, reproduced) |
| Env in the loop | no | **yes — the defining axis** |
| Staleness | re-run the pipeline | provenance-driven *selective* revalidation |

Plus what no prompt-only system has: **executed feedback** (refinement sees its
attempt's real failing output), **negative controls in CI** (flaky environments
are rejected, not certified), **honest accounting** (every number pre-registered
in the [claims ledger](https://github.com/JayLZhou/CausalData-Juicer/blob/main/experiments/claims.md) — nulls included, on the front page).

