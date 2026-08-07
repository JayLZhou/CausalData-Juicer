"""Core abstractions of CausalData-Juicer.

The four contribution-1 abstractions are ``Episode`` / ``Snapshot`` /
``Intervention`` / ``Outcome``.  The terminal data unit is the
evidence-graded ``CausalUnit``.  Evidence tiers are strictly ordered and
must remain visible wherever a unit is displayed or exported.
"""

from __future__ import annotations

import enum
import hashlib
import json
import uuid
from typing import Any, ClassVar

from pydantic import BaseModel, Field, field_serializer, field_validator


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def digest_of(obj: Any) -> str:
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(data.encode()).hexdigest()[:16]


class SideEffectClass(enum.StrEnum):
    """Side-effect grading of a tool.  EXTERNAL_SIDE_EFFECT tools are never
    truly re-executed during replay — only mocked / dry-run."""

    PURE = "PURE"
    IDEMPOTENT = "IDEMPOTENT"
    REVERSIBLE = "REVERSIBLE"
    TRANSACTIONAL = "TRANSACTIONAL"
    EXTERNAL_SIDE_EFFECT = "EXTERNAL_SIDE_EFFECT"


class EvidenceTier(enum.IntEnum):
    """Ordered evidence ladder.  Weak evidence must never masquerade as
    strong: every API/export surface carries ``tier.name``.

    Values are spaced by ten so a rung can be inserted without renumbering
    the ones above it — ``CONSTRAINT_VALIDATED`` was added between
    SUGGESTED and COUNTERFACTUAL_VALIDATED exactly this way. Runs written
    before that insertion stored small integers (0-5); those are remapped
    on load by :data:`LEGACY_TIER_VALUES`, and new runs persist the *name*,
    which no future insertion can reinterpret.
    """

    OBSERVED = 0
    SUGGESTED = 10
    #: LLM-generated and constraint-filtered — never a claim about the world.
    #: Only a real paired replay can lift a unit past this rung.
    CONSTRAINT_VALIDATED = 15
    COUNTERFACTUAL_VALIDATED = 20
    REPRODUCIBLE = 30
    MINIMAL = 40
    TRAINING_VALIDATED = 50


#: Wire format written before CONSTRAINT_VALIDATED existed (schema v1).
LEGACY_TIER_VALUES = {
    0: EvidenceTier.OBSERVED,
    1: EvidenceTier.SUGGESTED,
    2: EvidenceTier.COUNTERFACTUAL_VALIDATED,
    3: EvidenceTier.REPRODUCIBLE,
    4: EvidenceTier.MINIMAL,
    5: EvidenceTier.TRAINING_VALIDATED,
}


def parse_tier(value: Any) -> EvidenceTier:
    """Accept a name, a current value, or a legacy (0-5) integer."""
    if isinstance(value, EvidenceTier):
        return value
    if isinstance(value, str):
        return EvidenceTier[value]
    if isinstance(value, int):
        if value in EvidenceTier._value2member_map_:
            return EvidenceTier(value)
        if value in LEGACY_TIER_VALUES:
            return LEGACY_TIER_VALUES[value]
    raise ValueError(f"unrecognized evidence tier: {value!r}")


class CostLedger(BaseModel):
    """Cost accounting starts from line one.  Everything that spends
    tokens, seconds or dollars charges a ledger."""

    llm_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    tool_calls: int = 0
    replay_runs: int = 0
    wall_time_s: float = 0.0
    dollars: float = 0.0

    def charge_llm(self, tokens_in: int, tokens_out: int, dollars: float = 0.0) -> None:
        self.llm_calls += 1
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.dollars += dollars

    def charge_tool(self, wall_time_s: float) -> None:
        self.tool_calls += 1
        self.wall_time_s += wall_time_s

    def merge(self, other: CostLedger) -> None:
        self.llm_calls += other.llm_calls
        self.tokens_in += other.tokens_in
        self.tokens_out += other.tokens_out
        self.tool_calls += other.tool_calls
        self.replay_runs += other.replay_runs
        self.wall_time_s += other.wall_time_s
        self.dollars += other.dollars


class ToolCall(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)

    def signature(self) -> str:
        return digest_of({"tool": self.tool, "args": self.args})


class LLMRecord(BaseModel):
    """Recorded model interaction backing a step.  Replay never re-queries
    the model: responses are served from this cache."""

    model: str
    prompt: str
    response: str
    tokens_in: int = 0
    tokens_out: int = 0
    cached: bool = False  # served from disk cache: charged zero new cost
    dollars: float = 0.0


class Step(BaseModel):
    index: int
    action: ToolCall
    observation: str = ""
    obs_digest: str = ""
    snapshot_id: str | None = None  # snapshot of state *before* this step
    llm: LLMRecord | None = None
    wall_time_s: float = 0.0


class Outcome(BaseModel):
    success: bool
    detail: str = ""
    passed: int = 0
    failed: int = 0

    def signature(self) -> str:
        return digest_of({"success": self.success, "passed": self.passed, "failed": self.failed})


class Episode(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ep"))
    task_id: str
    workload_id: str = ""
    task_description: str = ""
    steps: list[Step] = Field(default_factory=list)
    outcome: Outcome | None = None
    final_tree_digest: str = ""
    cost: CostLedger = Field(default_factory=CostLedger)
    meta: dict[str, Any] = Field(default_factory=dict)


class Snapshot(BaseModel):
    """A snapshot is filesystem state + declared state at a step boundary.
    No promise of restoring a running process (no CRIU)."""

    id: str = Field(default_factory=lambda: new_id("snap"))
    episode_id: str
    step_index: int
    tree_digest: str
    declared_state: dict[str, Any] = Field(default_factory=dict)


class InterventionType(enum.StrEnum):
    ACTION_REPLACE = "ACTION_REPLACE"
    TOOL_ARGUMENT_EDIT = "TOOL_ARGUMENT_EDIT"


class LinePatch(BaseModel):
    """Replace line ``line`` (0-based) of a string argument with ``text``.
    Line patches are the atoms of causal slicing."""

    line: int
    text: str


class ArgEdit(BaseModel):
    arg: str
    op: str = "set"  # "set" | "patch_lines"
    value: Any | None = None
    patches: list[LinePatch] = Field(default_factory=list)


class Intervention(BaseModel):
    id: str = Field(default_factory=lambda: new_id("iv"))
    type: InterventionType
    target_step: int
    new_action: ToolCall | None = None  # ACTION_REPLACE
    edits: list[ArgEdit] = Field(default_factory=list)  # TOOL_ARGUMENT_EDIT
    rationale: str = ""
    source: str = ""  # e.g. "fixer-cache", "heuristic"

    def effect_signature(self) -> str:
        """Dedup key: two candidates proposing the same edit are one."""
        payload = {
            "type": self.type.value,
            "step": self.target_step,
            "new_action": self.new_action.model_dump() if self.new_action else None,
            "edits": [e.model_dump() for e in self.edits],
        }
        return digest_of(payload)


class ReplayRecord(BaseModel):
    branch: str  # "original" | "intervened"
    outcome: Outcome
    obs_digests: list[str] = Field(default_factory=list)
    deterministic_match: bool | None = None  # original branch only
    digest_match_fraction: float | None = None  # per-step match rate, original branch


class CausalUnit(BaseModel):
    """The terminal asset.  Its evidence tier travels with it everywhere."""

    id: str = Field(default_factory=lambda: new_id("cu"))
    episode_id: str
    task_id: str
    intervention: Intervention
    original_outcome: Outcome
    intervened_outcome: Outcome | None = None
    flipped: bool = False
    original_replay_match: bool | None = None
    control_digest_match: float | None = None  # step-level rate on the control branch
    repro_runs: int = 0
    repro_flips: int = 0
    tier: EvidenceTier = EvidenceTier.SUGGESTED

    @field_validator("tier", mode="before")
    @classmethod
    def _coerce_tier(cls, v: Any) -> EvidenceTier:
        return parse_tier(v)

    @field_serializer("tier")
    def _dump_tier(self, tier: EvidenceTier) -> str:
        # names survive rung insertions; the legacy integers did not
        return tier.name

    minimal_intervention: Intervention | None = None
    atoms_before_slicing: int = 0
    atoms_after_slicing: int = 0
    cost: CostLedger = Field(default_factory=CostLedger)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @property
    def tier_name(self) -> str:
        return self.tier.name

    def effective_intervention(self) -> Intervention:
        return self.minimal_intervention or self.intervention


# ---------------------------------------------------------------------------
# Identify -> Generate -> Filter -> Validate
#
# The mainstream counterfactual-data-augmentation pipeline, made explicit.
# Generation is cheap and unreliable; execution is expensive and decisive.
# These types keep the two apart, so a model-written branch can reach
# CONSTRAINT_VALIDATED on its own merits and no further.
# ---------------------------------------------------------------------------


class SiteKind(enum.StrEnum):
    """What sort of variable a site names."""

    TEXT_SPAN = "TextSpan"
    SEMANTIC_TRIPLE = "SemanticTriple"
    RATIONALE = "Rationale"
    AGENT_ACTION = "AgentAction"
    TOOL_ARGUMENT = "ToolArgument"
    STRUCTURED_FIELD = "StructuredField"


class InterventionSite(BaseModel):
    """A variable that *can* be intervened on, with the causal bookkeeping
    an honest ``do`` needs: what must stay fixed, and what is allowed to
    change downstream."""

    id: str = Field(default_factory=lambda: new_id("site"))
    episode_id: str = ""
    step_index: int = 0
    kind: SiteKind = SiteKind.TEXT_SPAN
    variable: str  # e.g. "tool_argument.version"
    current_value: str = ""
    influence_score: float = 0.0  # heuristic prior, never evidence
    invariants: list[str] = Field(default_factory=list)
    possible_descendants: list[str] = Field(default_factory=list)
    locator: dict[str, Any] = Field(default_factory=dict)  # how to edit it


class GenerationProvenance(BaseModel):
    """Who produced this branch, and how — recorded so a reviewer can tell
    a model's guess from an executed fact."""

    generator: str = "unknown"  # operator name
    strategy: str = ""
    model: str | None = None
    prompt_digest: str | None = None
    seed: int | None = None
    cached: bool = False
    regenerated_descendants: list[str] = Field(default_factory=list)


class ValidationVector(BaseModel):
    """Composable verdicts. Hard constraints gate promotion; soft scores
    rank. One LLM judge is never the whole story."""

    intervention_fidelity: bool | None = None
    target_outcome_shift: bool | None = None
    invariant_preservation: bool | None = None
    schema_validity: bool | None = None
    minimality: float | None = None
    semantic_proximity: float | None = None
    fluency: float | None = None
    diversity: float | None = None
    verifier_confidence: float | None = None
    accepted: bool = False
    failed_at: str | None = None
    reason: str = ""

    #: Checked as a cascade, most fundamental first, so ``failed_at`` names
    #: the real problem: an unexecutable action is not an invariant bug.
    HARD: ClassVar[tuple[str, ...]] = (
        "schema_validity",
        "intervention_fidelity",
        "invariant_preservation",
        "target_outcome_shift",
    )

    def first_failure(self) -> str | None:
        for name in self.HARD:
            value = getattr(self, name)
            if value is False:
                return name
        return None


class GeneratedBranch(BaseModel):
    """A model-proposed counterfactual: an intervention plus everything a
    reviewer (or a filter) needs to judge it *before* paying for a replay."""

    id: str = Field(default_factory=lambda: new_id("gb"))
    episode_id: str
    task_id: str = ""
    site_id: str = ""
    site: InterventionSite | None = None
    intervention: Intervention
    target_outcome: str = "success"  # what this do() is meant to achieve
    invariants: list[str] = Field(default_factory=list)
    provenance: GenerationProvenance = Field(default_factory=GenerationProvenance)
    validation: ValidationVector | None = None
    tier: EvidenceTier = EvidenceTier.SUGGESTED

    @field_validator("tier", mode="before")
    @classmethod
    def _coerce_tier(cls, v: Any) -> EvidenceTier:
        return parse_tier(v)

    @field_serializer("tier")
    def _dump_tier(self, tier: EvidenceTier) -> str:
        return tier.name

    def effect_signature(self) -> str:
        """Branches that intervene on the same variable in the same way are
        one experiment; the selector spends budget per signature, not per
        duplicate."""
        iv = self.intervention
        payload = {
            "episode": self.episode_id,
            "step": iv.target_step,
            "type": str(iv.type),
            "variable": (self.site.variable if self.site else self.site_id),
            "value": digest_of(
                iv.new_action.model_dump() if iv.new_action else [e.model_dump() for e in iv.edits]
            ),
        }
        return digest_of(payload)


class ReplayRequest(BaseModel):
    """A branch the selector judged worth real execution, with the reasoning
    that bought it the slot."""

    branch_id: str
    episode_id: str
    effect_signature: str
    priority: float = 0.0
    estimated_cost: float = 1.0
    rationale: str = ""
    is_cluster_representative: bool = False
