# Paper skeleton — CausalData-Juicer

**Working title:** *CausalData-Juicer: A Budgeted Interventional Data Engine
for Agent Improvement*
**Target venue class:** NeurIPS Datasets & Benchmarks / MLSys (systems +
benchmark + empirical findings). Fallback: arXiv tech report with the release.

Every results claim below cites a row of `experiments/claims.md` — the ledger
IS the results section skeleton. No number appears in the paper that is not in
the ledger with a pre-registered threshold.

## 1. Introduction
- Experience systems process logs that happened; agents need experience that
  *should* have happened. Interventional acquisition as the missing axis.
- Contributions: (C1) operator algebra `(Units, Env, Budget) → Units'` with an
  enforced evidence ladder; (C2) the engine: paired counterfactual replay with
  a determinism gate, budget layer, selective revalidation; (C3) empirical
  acquisition science (source diversity/fidelity/stochasticity); (C4)
  expressiveness: six ≤80-line reproductions of published data engines;
  (C5) a doubly-certified migration bench methodology.

## 2. Related work
- Data-Juicer family (DJ 2.0, Sandbox, Trinity-RFT) — observational algebra.
- Branch-and-rollout data construction: MCTS→DPO, TreeRL/Tree-GRPO, RTMC,
  AT2PO, CCPO, CriticSearch, CAPER. Each hand-builds our loop (Table: family →
  our expression; already in README).
- Replay/record systems, delta debugging (ddmin), HER, PRMs.

## 3. Abstractions (C1)
- Episode / Snapshot / Intervention / Outcome / CausalUnit; evidence ladder;
  access tiers as operator subsets with ceilings; side-effect classes.
- Figure 1: the closed loop. Figure 2: operator algebra table (from README zoo).

## 4. Engine (C2)
- Paired replay + determinism gate (A1, A9, A13 negative controls).
- Budget layer: mechanisms (A7 ablation, 26%) + policies (A7 at 295: tight-
  budget advantage, convergence). Figure: cost-per-unit curves (m2_curves*.json).
- Storage: implicit trace DAG, checkpoint placement (A6, 298×; dag stats).
- Maintenance: dependency-claim provenance, selective revalidation under two
  real version events (A8, 4.8×/8.0×, zero missed demotions; control-drift
  demotion class). Figure: revalidation event diagram.

## 5. The bench (C5)
- 52 tasks / 6 families; pass-old/fail-new double certification; hermeticity;
  anti-cheat seals. Sidebar: five famous breaking changes that don't break
  (GenericModel, np.trapz, Query.get, click quotes/underscores).

## 6. Acquisition science (C3)
- A10 layered: source diversity vs fixer strength by difficulty tier.
- A12 fidelity ladder incl. validation-in-the-loop refinement (executed
  feedback), test-aware prompting first cracking a T3.
- The n06 story: stochastic sources pierce the deterministic ceiling; k=8
  separation of sampling-starved vs method-limited failures (A14).
- A11: failure profiles nest by agent capability (mid-tier collector choice).
- Figure: coverage waterfall by source; Table: 24/35 conversion.

## 7. Expressiveness (C4)
- Six reproductions (43–78 lines) incl. same-day CAPER; repair/stress symmetry
  demonstrated on one machine. Table from README showcase.

## 8. Training-value pilot (honest null)
- C1 design (matched-token, same-distribution, cross-family holdout), result
  (exact tie, 15/16 identical), power analysis, re-test conditions. Frame:
  the ledger culture demands publishing this.

## 9. Limitations & future
- Single-language bench core (SQL case partially offsets); no live-process
  snapshots (no CRIU); C-chain underpowered; adoption pending.

## Figures/tables inventory
1. Closed-loop diagram; 2. operator algebra; 3. cost-per-unit curves;
4. revalidation events; 5. coverage-by-source waterfall; 6. reproduction
table; 7. bench certification table; 8. C1 arms.

## TODO before submission
- [ ] Related-work pass with citations (the family list is in README_ZH).
- [ ] Figures 1/4/5 need drawing; 3 exists as JSON → plot.
- [ ] Optional strengtheners: one external workload anchor; stress-direction
      mini-eval beyond the CAPER demo.
