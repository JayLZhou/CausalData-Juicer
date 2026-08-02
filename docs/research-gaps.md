# Causal-operation coverage map: what we express, what we don't (yet)

A survey of causal/counterfactual operations across ML — beyond the
data-construction landscape already covered — asking one question per
family: **can our algebra `(Units, Env, Budget) → Units'` express it, and
what operator is missing if not?** All references verified against
arXiv/proceedings/code (2026-08-02).

## S1 · Causal data SELECTION / valuation / attribution (training-data influence)

The family the engine does not yet touch: which *existing* training examples
causally drive model behavior?

| Paper | Venue | Links | Counterfactual operation |
|---|---|---|---|
| Understanding Black-box Predictions via Influence Functions | ICML 2017 | [arXiv](https://arxiv.org/abs/1703.04730) · [code](https://github.com/kohpangwei/influence-release) | leave-one-out retraining approximated by inverse-Hessian-vector products |
| Data Shapley | ICML 2019 | [arXiv](https://arxiv.org/abs/1904.02868) · [code](https://github.com/amiratag/DataShapley) | marginal contribution averaged over subset re-trainings (Monte Carlo) |
| TRAK: Attributing Model Behavior at Scale | ICML 2023 | [arXiv](https://arxiv.org/abs/2303.14186) · [code](https://github.com/MadryLab/trak) | linearized surrogate predicts outputs under changed training subsets |
| DsDm: Model-Aware Dataset Selection with Datamodels | ICML 2024 | [arXiv](https://arxiv.org/abs/2401.12926) · [code](https://github.com/MadryLab/dsdm) | learned include/exclude → loss surrogate, optimized for subset selection |
| LESS: Selecting Influential Data for Targeted Instruction Tuning | ICML 2024 | [arXiv](https://arxiv.org/abs/2402.04333) · [code](https://github.com/princeton-nlp/LESS) | gradient-similarity influence of candidates on target-task loss |
| DataInf | ICLR 2024 | [arXiv](https://arxiv.org/abs/2310.00902) · [code](https://github.com/ykwon0407/DataInf) | closed-form leave-one-out estimates for LoRA-tuned models |

**Fit analysis.** Every method approximates one ground-truth operation —
*re-execute training with a modified data manifest, diff the outputs* —
which is exactly our intervention semantics with training-as-environment.
**Missing operator:** `train_replay` — deterministic training re-execution
from recorded checkpoints with a data-manifest intervention (fixed seeds,
batching, optimizer state), plus per-example gradient exposure. With it,
the engine (a) provides *exact* counterfactual ground truth to validate the
cheap estimators on small scales, and (b) turns influence estimation into
cached intervention queries. Natural first case study: validate LESS-style
selection on our own C1 LoRA runs (the training loop is already in
`experiments/c1_train.py`). Priority: **high** — closest to our existing
machinery and directly serves the data-selection user base.

## S2 · Model-internal causal interventions (activation/weight level)

| Paper | Venue | Links | Counterfactual operation |
|---|---|---|---|
| ROME: Locating and Editing Factual Associations in GPT | NeurIPS 2022 | [arXiv](https://arxiv.org/abs/2202.05262) · [code](https://github.com/kmeng01/rome) | causal tracing: restore clean activations into a corrupted run per (layer, token), measure recovery |
| Interpretability in the Wild (IOI) | ICLR 2023 | [arXiv](https://arxiv.org/abs/2211.00593) · [code](https://github.com/redwoodresearch/Easy-Transformer) | path patching of attention heads between counterfactual prompts |
| Causal Abstractions of Neural Networks | NeurIPS 2021 | [arXiv](https://arxiv.org/abs/2106.02997) · [pyvene](https://github.com/stanfordnlp/pyvene) | interchange interventions; origin of interchange-intervention accuracy |
| DAS: Distributed Alignment Search | CLeaR 2024 | [arXiv](https://arxiv.org/abs/2303.02536) · [code](https://github.com/frankaging/align-transformers) | learned-subspace interchange interventions |
| Attribution Patching Outperforms ACDC | BlackboxNLP 2024 | [arXiv](https://arxiv.org/abs/2310.10348) · [code](https://github.com/Aaquib111/edge-attribution-patching) | linearized (gradient) approximation of activation patching, validated against true patching |
| Function Vectors in LLMs | ICLR 2024 | [arXiv](https://arxiv.org/abs/2310.15213) · [code](https://github.com/ericwtodd/function_vectors) | causal mediation over ICL heads; vector causally validated by patching into unrelated runs |

**Fit analysis.** Structurally identical to our loop — two recorded
executions, splice a snapshot of one into the other at a program point,
diff outputs — but the *host* is a forward pass, not a filesystem: it needs
activation snapshot/restore (torch hooks) and gradient access, which our
sandbox does not provide. `pyvene` already serves this niche well.
**Missing operator:** a `forward_replay` host — worth building only as a
thin adapter whose value-add is our evidence ladder + budget metering over
patching experiments, not the patching itself. Priority: **low** (explicit
scope boundary today; revisit if interp users ask).

## S3 · Counterfactual data beyond the LLM world

| Sub-area | Paper | Venue | Links | Counterfactual operation |
|---|---|---|---|---|
| OPE / logged bandits | Open Bandit Dataset & Pipeline | NeurIPS 2021 D&B | [arXiv](https://arxiv.org/abs/2008.07146) · [code](https://github.com/st-tech/zr-obp) | multi-policy logs let "what would policy B earn" be checked against B's real logs |
| Counterfactual LTR | Unbiased Learning-to-Rank with Biased Feedback | WSDM 2017 | [arXiv](https://arxiv.org/abs/1608.04468) · no official code | inverse-propensity reweighting reconstructs unbiased click data |
| XAI | Wachter et al., Counterfactual Explanations & the GDPR | Harvard JOLT 2018 | [arXiv](https://arxiv.org/abs/1711.00399) · no official code | closest input change that flips the decision |
| XAI | DiCE | ACM FAT* 2020 | [arXiv](https://arxiv.org/abs/1905.07697) · [code](https://github.com/interpretml/DiCE) | diverse feasibility-constrained flipping inputs |
| Deep SCM | Deep Structural Causal Models | NeurIPS 2020 | [arXiv](https://arxiv.org/abs/2006.06485) · [code](https://github.com/biomedia-mira/deepscm) | full abduction–action–prediction counterfactual images |
| Causal augmentation | Counterfactual Generative Networks | ICLR 2021 | [arXiv](https://arxiv.org/abs/2101.06046) · [code](https://github.com/autonomousvision/counterfactual_generative_networks) | recombined independent mechanisms (shape/texture/background) as OOD-robust training data |
| Econometrics | Synthetic Control (Abadie et al.) | JASA 2010 | [DOI](https://www.tandfonline.com/doi/abs/10.1198/jasa.2009.ap08746) · [CRAN Synth](https://cran.r-project.org/web/packages/Synth/index.html) | counterfactual trajectory as weighted donor combination |
| RL augmentation | CoDA: Counterfactual Data Augmentation | NeurIPS 2020 | [arXiv](https://arxiv.org/abs/2007.02863) · [code](https://github.com/spitis/mrl) | stitch causally independent sub-components of stored transitions into valid new transitions |

**Fit analysis.** XAI counterfactuals, deep SCMs and CoDA map directly onto
fork → alternative → compare (XAI flip-search is literally our stress
direction over input features; CoDA is a snapshot-recombination operator).
OPE and synthetic control are the **opposite regime — the system cannot be
re-run**, so counterfactuals must be estimated rather than executed; they
define precisely what a replay engine buys: *direct observation of the
counterfactual instead of statistical estimation of it* (Open Bandit paid
for that observation by running multiple live policies). **Missing
operators:** `input_flip_search` (XAI/stress over structured inputs —
medium priority, shares machinery with our v2 stress direction) and
`transition_stitch` (CoDA-style recombination — low priority). Dreamer-line
"imagination" was checked and excluded: no counterfactual framing in the
papers themselves.

## S4 · Remaining causal ops inside LLM/agent pipelines

| Sub-area | Paper | Venue | Links | Counterfactual operation |
|---|---|---|---|---|
| RAG attribution | ContextCite | NeurIPS 2024 | [arXiv](https://arxiv.org/abs/2409.00729) · [code](https://github.com/MadryLab/context-cite) | ablate context-source subsets, re-score, fit sparse surrogate per source |
| Prompt components | Rethinking the Role of Demonstrations | EMNLP 2022 | [arXiv](https://arxiv.org/abs/2202.12837) · [code](https://github.com/Alrope123/rethinking-demonstrations) | swap labels/format/distribution of demos, re-run inference |
| CoT (un)faithfulness | LMs Don't Always Say What They Think | NeurIPS 2023 | [arXiv](https://arxiv.org/abs/2305.04388) · [code](https://github.com/milesaturpin/cot-unfaithfulness) | biased-vs-unbiased prompt pairs expose omitted causes |
| CoT step credit | Measuring Faithfulness in CoT (Lanham et al.) | arXiv preprint | [arXiv](https://arxiv.org/abs/2307.13702) · no official code | truncate/corrupt/paraphrase a reasoning step, re-generate the answer |
| CoT step credit | Thought Anchors | arXiv preprint (ICLR'26 sub) | [arXiv](https://arxiv.org/abs/2506.19143) · [code](https://github.com/interp-reasoning/thought-anchors) | resample a sentence, roll out the rest, diff answer distribution |
| RM debiasing | RRM: Robust Reward Model Training | ICLR 2025 | [arXiv](https://arxiv.org/abs/2409.13156) · no official code | artifact-swapped counterfactual preference pairs |
| Tool attribution | AgentSHAP | arXiv preprint | [arXiv](https://arxiv.org/abs/2512.12597) · [code](https://github.com/ronigold/TokenSHAP) | tool on/off subsets, Monte-Carlo Shapley per tool |

**Fit analysis.** Six of seven are *directly* our loop — edit one element
of a logged run (a retrieved document, a reasoning step, a prompt feature,
a tool's availability), re-execute from that point, diff the outcome. With
reactive continuation just landed, Thought-Anchors-style step resampling is
our `ResampleSource` + `continuation_policy` verbatim. RRM is the
exception (offline pair construction, no replay).

## Synthesis: the operator wishlist, ranked

| Rank | Missing operator | Serves | Effort | Note |
|---|---|---|---|---|
| 1 | `context_ablate` (drop/keep elements of retrieved context or prompt, re-execute) | ContextCite, Min et al., RAG users | **~1 case study** — machinery exists | most immediate adoption surface (every RAG team wants this) |
| 2 | `step_resample_credit` (CoT sentence-level Thought-Anchors) | Lanham, Thought Anchors | **~1 case study** — reactive replay + resample exist | reasoning-model era demand |
| 3 | `tool_ablate` (enable/disable tools per replay, Shapley over subsets) | AgentSHAP | small (registry intervention + prep hook) | agent-platform demand |
| 4 | `train_replay` (deterministic training re-execution with data-manifest interventions) | the whole S1 selection/valuation family | medium (seeded training loop + checkpointing; C1 code is the seed) | highest strategic value: exact ground truth for influence estimators |
| 5 | `input_flip_search` (XAI/stress flip-search over structured inputs) | DiCE lineage + our v2 stress | medium | shares machinery with stress direction |
| 6 | `transition_stitch` (CoDA recombination) | RL augmentation | medium | niche for us today |
| 7 | `forward_replay` (activation snapshot/restore host) | S2 interp family | large | pyvene owns this niche; only as thin evidence-tier adapter |

**Bottom line.** The sweep found one big strategic gap (S1: causal data
selection — the engine can become the *ground-truth machine* the whole
influence-estimation family lacks) and three nearly-free case studies
(ranks 1–3) that each open a distinct user community with machinery we
already shipped this week.
