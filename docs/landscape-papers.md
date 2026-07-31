# The counterfactual data-construction landscape: verified references

Companion to the landscape table on the front page. Every entry below was
verified against its arXiv/OpenReview page and its code repository checked
for existence at collection time (2026-08-01). Venue is as stated in the
paper's official metadata; "arXiv preprint" means no acceptance was found.

## A · Step-level credit in reasoning

| Paper | Venue | Links | Counterfactual data constructed |
|---|---|---|---|
| Let's Verify Step by Step (PRM800K) | ICLR 2024 | [arXiv](https://arxiv.org/abs/2305.20050) · [data](https://github.com/openai/prm800k) | 800K *human-annotated* step labels — the PRM origin (not branching; cited as reference point) |
| Math-Shepherd | ACL 2024 | [arXiv](https://arxiv.org/abs/2312.08935) · datasets on HF (no official training code) | step labels from N branched completions per step (Monte-Carlo correctness) |
| Step-DPO | arXiv preprint | [arXiv](https://arxiv.org/abs/2406.18629) · [code](https://github.com/JIA-Lab-research/Step-DPO) | first-error step paired with corrected continuation from the same prefix (10K pairs) |
| MCTS Boosts Reasoning via Iterative Preference Learning | NeurIPS 2024 *workshop* (Sys-2 Reasoning; often mis-cited as main) | [arXiv](https://arxiv.org/abs/2405.00451) · [code](https://github.com/YuxiXie/MCTS-DPO) | step-level preference pairs from MCTS sibling branches |
| AlphaMath Almost Zero | NeurIPS 2024 | [arXiv](https://arxiv.org/abs/2405.03553) · [code](https://github.com/MARIO-Math-Reasoning/Super_MARIO) | step-level Q estimates from MCTS rollouts, zero human annotation |
| rStar-Math | ICML 2025 (oral) | [arXiv](https://arxiv.org/abs/2501.04519) · [code](https://github.com/microsoft/rStar) | Q-annotated reasoning trees → process preference model, self-evolved |

## B · Advantage signals for agent RL (rollout trees / counterfactual credit)

| Paper | Venue | Links | Counterfactual data constructed |
|---|---|---|---|
| TreeRL | ACL 2025 | [arXiv](https://arxiv.org/abs/2506.11902) · [code](https://github.com/THUDM/TreeRL) | on-policy trees branched at high-entropy steps → dense process rewards |
| Tree-GRPO | ICLR 2026 | [arXiv](https://arxiv.org/abs/2509.21240) · [code](https://github.com/AMAP-ML/Tree-GRPO) | prefix-sharing agent-step trees; intra/inter-tree group advantages |
| ARPO | ICLR 2026 | [arXiv](https://arxiv.org/abs/2507.19849) · [code](https://github.com/RUC-NLPIR/ARPO) | entropy-adaptive branching after tool calls; shared-vs-branched advantage attribution |
| GiGPO | NeurIPS 2025 | [arXiv](https://arxiv.org/abs/2505.10978) · [code](https://github.com/langfengQ/verl-agent) | anchor-state grouping across rollouts = implicit same-state counterfactuals, critic-free |
| AT²PO | ACL 2026 | [arXiv](https://arxiv.org/abs/2601.04767) · [code](https://github.com/zzfoutofspace/ATPO) | turn-level rollout trees, entropy-guided; outcome rewards back-propagated per turn |
| CCPO | arXiv preprint | [arXiv](https://arxiv.org/abs/2603.21563) · [code](https://github.com/bhai114/ccpo) | joint outcome vs counterfactual rollouts with one agent's contribution removed |
| RTMC | arXiv preprint | [arXiv](https://arxiv.org/abs/2604.11037) · no official code | implicit rollout trees via state-action signatures → critic-free per-step Q |

## C · Repair data for code agents (patch-vs-outcome execution)

| Paper | Venue | Links | Counterfactual data constructed |
|---|---|---|---|
| SWE-RL: Advancing LLM Reasoning via RL on Open Software Evolution | NeurIPS 2025 | [arXiv](https://arxiv.org/abs/2502.18449) · [code](https://github.com/facebookresearch/swe-rl) | patches scored against oracle merged patches from GitHub evolution histories |
| Training SWE Agents and Verifiers with SWE-Gym | ICML 2025 | [arXiv](https://arxiv.org/abs/2412.21139) · [code](https://github.com/SWE-Gym/SWE-Gym) | 2,438 executable tasks; sampled patches executed against unit tests → success/failure-labeled trajectories |
| SWE-smith: Scaling Data for Software Engineering Agents | NeurIPS 2025 D&B (Spotlight) | [arXiv](https://arxiv.org/abs/2504.21798) · [code](https://github.com/SWE-bench/SWE-smith) | ~50k bug-injection patches, each validated by executing the repo test suite |
| RepairLLaMA: Efficient Representations and Fine-Tuned Adapters for Program Repair | IEEE TSE | [arXiv](https://arxiv.org/abs/2312.15698) · [code](https://github.com/ASSERT-KTH/repairllama) | buggy/fixed pairs from bug-fix commits; candidate patches judged by executing test suites |

## D · Process supervision for structured generation (Text-to-SQL)

| Paper | Venue | Links | Counterfactual data constructed |
|---|---|---|---|
| CAPER: Clause-Aligned Process Supervision for Text-to-SQL | arXiv preprint | [arXiv](https://arxiv.org/abs/2606.03327) · official code link 404s (our [77-line reproduction](https://github.com/JayLZhou/CausalData-Juicer/blob/main/examples/case_caper_clause_prm.py)) | counterfactual interventions on SQL ASTs; executed clause variants isolate the culpable clause |
| SQL-R1: Training NL2SQL Reasoning by RL | NeurIPS 2025 | [arXiv](https://arxiv.org/abs/2504.08600) · [code](https://github.com/DataArcTech/SQL-R1) | every rollout executed against the database, scored on result correctness |
| Reward-SQL: Stepwise Execution-Aware Reasoning and Process-Supervised Rewards | arXiv preprint | [arXiv](https://arxiv.org/abs/2505.04671) · [code](https://github.com/ruc-datalab/RewardSQL) | partial programs (CTE steps) executed to train a process reward model |
| Arctic-Text2SQL-R1: Simple Rewards, Strong Reasoning | arXiv preprint | [arXiv](https://arxiv.org/abs/2505.20315) · [code](https://github.com/snowflakedb/ArcticTraining) | execution-correctness reward: each generated query run against the DB |

## E · Supervision recycled from failures (hindsight relabeling)

| Paper | Venue | Links | Counterfactual data constructed |
|---|---|---|---|
| Hindsight Experience Replay | NeurIPS 2017 | [arXiv](https://arxiv.org/abs/1707.01495) · [code](https://github.com/openai/baselines) | failed trajectories relabeled with the goals actually reached |
| The Wisdom of Hindsight Makes LMs Better Instruction Followers (HIR) | ICML 2023 | [arXiv](https://arxiv.org/abs/2302.05206) · [code](https://github.com/tianjunz/HIR) | instructions rewritten so failed outputs become correct supervision |
| Trial and Error: Exploration-Based Trajectory Optimization (ETO) | ACL 2024 | [arXiv](https://arxiv.org/abs/2403.02502) · [code](https://github.com/Yifan-Song793/ETO) | failure–success contrastive trajectory pairs for DPO |
| Chain of Hindsight Aligns LMs with Feedback | ICLR 2024 | [arXiv](https://arxiv.org/abs/2302.02676) · [code](https://github.com/haoliuhl/chain-of-hindsight) | good/bad outputs plus feedback turned into hindsight-annotated sequences |

## F · Robustness & stress-direction data

| Paper | Venue | Links | Counterfactual data constructed |
|---|---|---|---|
| CheckList: Behavioral Testing of NLP Models | ACL 2020 | [arXiv](https://arxiv.org/abs/2005.04118) · [code](https://github.com/marcotcr/checklist) | invariance/directional perturbation suites that break models |
| Counterfactually-Augmented Data | ICLR 2020 | [arXiv](https://arxiv.org/abs/1909.12434) · [code](https://github.com/acmi-lab/counterfactually-augmented-data) | minimal human edits that flip the gold label |
| Adversarial NLI (ANLI) | ACL 2020 | [arXiv](https://arxiv.org/abs/1910.14599) · [code](https://github.com/facebookresearch/anli) | human-in-the-loop examples that break the current model, folded back as training data |
| Polyjuice | ACL-IJCNLP 2021 | [arXiv](https://arxiv.org/abs/2101.00288) · [code](https://github.com/tongshuangwu/polyjuice) | controlled automated minimal perturbations |

## G · Credit & blame in multi-agent systems

| Paper | Venue | Links | Counterfactual data constructed |
|---|---|---|---|
| Counterfactual Multi-Agent Policy Gradients (COMA) | AAAI 2018 | [arXiv](https://arxiv.org/abs/1705.08926) · [code (PyMARL)](https://github.com/oxwhirl/pymarl) | counterfactual baseline marginalizing one agent's action, others fixed |
| Which Agent Causes Task Failures and When? (Who&When) | ICML 2025 | [arXiv](https://arxiv.org/abs/2505.00212) · [code](https://github.com/mingyin1/Agents_Failure_Attribution) | failure logs from 127 LLM-MAS with human-annotated culpable agent + decisive step |
| Why Do Multi-Agent LLM Systems Fail? (MAST) | NeurIPS 2025 D&B | [arXiv](https://arxiv.org/abs/2503.13657) · [code](https://github.com/multi-agent-systems-failure-taxonomy/MAST) | 14-mode failure taxonomy from 1600+ annotated traces |
| Agents that Matter: Removal-Based Attribution | arXiv preprint | [arXiv](https://arxiv.org/abs/2605.27621) · no official code | leave-one-out / Shapley-style agent-removal counterfactuals |

## H · Skill & memory libraries

| Paper | Venue | Links | Experience data constructed |
|---|---|---|---|
| Voyager | TMLR 2024 | [arXiv](https://arxiv.org/abs/2305.16291) · [code](https://github.com/MineDojo/Voyager) | executable skill library; skills self-verified in-env before storage |
| CLIN | COLM 2024 | [arXiv](https://arxiv.org/abs/2310.10134) · [code](https://github.com/allenai/clin) | causal-abstraction memory ("X is necessary for Y") revised per trial outcome |
| ExpeL: LLM Agents Are Experiential Learners | AAAI 2024 | [arXiv](https://arxiv.org/abs/2308.10144) · [code](https://github.com/LeapLabTHU/ExpeL) | insights distilled from paired success/failure experiences |
| Agent Workflow Memory | ICML 2025 | [arXiv](https://arxiv.org/abs/2409.07429) · [code](https://github.com/zorazrw/agent-workflow-memory) | reusable workflows induced from past successful trajectories |
