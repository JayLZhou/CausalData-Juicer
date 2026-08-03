# SIGMOD(-industrial) packaging plan — following Data-Juicer's template

Template source: Data-Juicer, SIGMOD 2024 (arXiv:2309.02033). Their winning
move: an ML-adjacent story told as a **data systems** paper — abstractions,
optimizations, reproducibility, ecosystem integration — with a challenge-driven
intro (C1–C4) and a nine-experiment catalog.

## 1 · Framing translation

| Data-Juicer said | We say |
|---|---|
| "one-stop data processing system for LLMs" | "an interventional data engine for agent experience" |
| users = model developers & data practitioners | users = agent developers, RL-data teams, agent-platform operators |
| C1 heterogeneity · C2 feedback loops · C3 usability · C4 volume | **C1 validity** (when is a counterfactual comparison trustworthy) · **C2 cost** (every branch is a real execution) · **C3 staleness** (validated data expires with the environment) · **C4 expressibility** (one algebra, many published strategies) |
| operator pool, `Dataset → Dataset` | operator zoo, `(Units, Env, Budget) → Units'` — the interventional extension is *the* systems-novelty claim |
| zero-/low-/advanced-code user tiers | Import Mode / Tool Replay / Snapshot Mode — same segmentation, plus enforced evidence ceilings (ours carries semantics, not just ergonomics) |

## 2 · Section mapping (theirs → ours)

1. Intro w/ C1–C4 → ours w/ validity/cost/staleness/expressibility
2. Background & related → landscape (29 refs) + coverage map (27 refs)
3. Standardized operator pool → §3 algebra + zoo (4 categories, DJ-style registry & YAML recipes — cite the lineage explicitly)
4. Feedback-driven processing (HPO, checkpoints, caching) → §4 engine: determinism gate, budget mechanisms/policies, checkpoint placement, LLM cache, selective revalidation
5. Usability built-ins → §5 three doors, `doctor`/`explain`/`verify-claims`, recipes, replay packs
6. System optimization → folded into §4 with ablations
7. Evaluation → experiment catalog below
8. Deployment/industrial → dogfooding + external-tester round + ecosystem exports

## 3 · Experiment catalog mapping

| DJ experiment | Our equivalent | Status |
|---|---|---|
| E1/E2 data-recipe quality → model wins (their crown jewel) | (a) validity guarantees as the quality claim (13-config 100% flip-repro, dual-certified bench); (b) C1 training pilot — **honest replicated null**, framed as scale-bounded; (c) **NEW: memory-retrieval eval** — do failure→recovery units, retrieved as memory, raise agent solve rate on similar held-out tasks? Training-free downstream value, runnable on our infra | (a)✅ (b)✅ (c)✅ **ran 2026-08-03**: baseline 6/16×2 vs memory 8/16·7/16, robust task-level gains k08/k10, honest loss s04 → claims C2 |
| E3 end-to-end efficiency vs competitor codebases | vs the "per-paper hand-built loop" = no-mechanism ablation: 137→101 replays (−26%); cost-per-unit ≈3s/$0 | ✅ |
| E4 context mgmt / op fusion ablations | control-branch memoization + early-stop ablations | ✅ |
| E5 cache & checkpoint effectiveness | checkpoint placement (298×/1.91× vs from-scratch, byte-identical reconstruction); LLM cache → byte-exact offline replay packs | ✅ |
| E6 distributed scalability (Ray, 7.91×) | **NEW: worker-scaling curve** for parallel validation (workers = 1/2/4/8) | ✅ 5.3× @ 8 workers, outputs identical at all widths → claims A15 |
| E7 quality-classifier validation | determinism-gate validation: CI negative controls (flaky env rejected), anti-cheat seals (observed reward hacking caught) | ✅ |
| E8 operator coverage & usability | zoo (11 registered ops), 9 reproductions ≤110 lines incl. same-day CAPER, YAML recipes, 97-line front page | ✅ |
| E9 production deployment | gap: no production story yet → industrial section = dogfooding friction log (6 real fixes), external-tester round (D10 protocol ready), ecosystem exports (TRL/verl/DJ) | partial — D10 needs humans |

## 4 · Industrial-track checklist

- [x] Ecosystem integration: TRL / verl / Data-Juicer / Import-Mode schema
- [x] Config-driven reproducibility: YAML recipes + claims ledger + verify-claims
- [x] Segmented user model with three tiers
- [x] Open-source release engineering (license, CI, docs site, packaging dry-run)
- [ ] Deployment/adoption numbers (blocked on launch + testers)
- [x] The two new experiments above (worker scaling 5.3× A15; memory-retrieval eval C2)

## 5 · Honest deltas from the template

DJ's crown jewel is "refined data → better pretrained model," bought with
serious pretraining budget. We cannot match that scale; our crown jewels are
**validity machinery** (they have none — no control branches, no evidence
tiers, no staleness semantics) and **expressibility** (nine reproductions).
The memory-retrieval eval is our budget-realistic downstream-value play;
the C1 null stays in the paper as a scale-bounded honest result.
