# Case studies: six reproductions

Each case fills the same ten-line skeleton with a different candidate source
and label compiler. All run end-to-end with real execution; outputs are
archived under `experiments/results/`.

| Strategy family | File | Lines | What it produced |
|---|---|---|---|
| MCTS → step-level DPO | `examples/case_step_dpo.py` | 76 | 12 same-state preference pairs from live temperature sampling + replay |
| Rollout-tree credit (Tree-GRPO / RTMC) | `examples/case_rollout_tree.py` | 78 | depth-2 executed trees; level-2 conditioned on each branch's *executed* failure output; group-relative advantages |
| Counterfactual credit / ATE (CCPO) | `examples/case_credit_ate.py` | 53 | 9 credit-annotated trajectories, compiled offline from stored paired outcomes |
| Process-reward labels | byproduct of `case_step_dpo.py` | — | 46 executed-branch PRM labels |
| HER-style relabeling | `examples/case_her_relabel.py` | 43 | 34 achieved-goal supervision rows — zero replay, zero LLM, OBSERVED tier enforced |
| CAPER clause-level PRM (arXiv:2606.03327) | `examples/case_caper_clause_prm.py` | 77 | clause criticality in **both directions** — reproduced same-day from a June-2026 paper |

Three findings the case studies produced along the way:

- **Source diversity beats model strength** on easy/medium failures: cheap
  temperature resampling of a 7B flips tasks an entire 7B+14B fixer pool
  missed — and later pierced a "capability ceiling" the whole deterministic
  ladder (test-aware prompts, iterative refinement) could not.
- **Validation-in-the-loop refinement** is a capability no prompt-only system
  has: the fixer sees its own attempt's *executed* failing output and revises.
- **Repair and stress are the same machinery** with opposite sign: the CAPER
  case runs fail→pass attribution and pass→fail clause criticality through
  the identical replay path.
