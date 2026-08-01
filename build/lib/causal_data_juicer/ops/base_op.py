"""Data-Juicer-style operator framework.

Every operator is a registered class with a uniform ``run(ctx) -> ctx``
interface, discoverable by name, instantiated from params, and
composable into YAML recipes (``cdj process --config recipe.yaml``) —
the Data-Juicer developer experience, carried onto the interventional
signature ``(Units, Env, Budget) → Units'``.

Categories mirror the algebra:
  observational  no environment, zero budget, evidence ceiling ≤ SUGGESTED
  source         propose interventions (LLM cost, no execution)
  interventional execute the environment, spend budget, raise tiers
  compile        materialize views, tier-preserving
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Type

from causal_data_juicer.sdk.schemas import CostLedger


@dataclass
class OpContext:
    """The state a recipe threads through its operators."""

    workdir: Path
    episodes: list = field(default_factory=list)
    snapshots: list = field(default_factory=list)
    candidates: list = field(default_factory=list)   # (episode, intervention)
    units: list = field(default_factory=list)
    sources: list = field(default_factory=list)      # candidate sources for `screen`
    exports: dict = field(default_factory=dict)
    ledger: CostLedger = field(default_factory=CostLedger)
    services: dict = field(default_factory=dict)     # lazily built engine parts
    meta: dict = field(default_factory=dict)


class Op:
    """Base operator. Subclasses set ``category`` and implement ``run``."""

    category: str = "base"
    _op_name: str = ""

    def __init__(self, **params: Any):
        self.params = params

    def run(self, ctx: OpContext) -> OpContext:  # pragma: no cover - interface
        raise NotImplementedError

    def summary(self, ctx: OpContext) -> str:
        return (f"episodes={len(ctx.episodes)} candidates={len(ctx.candidates)} "
                f"units={len(ctx.units)} replays={ctx.ledger.replay_runs}")


class ObservationalOp(Op):
    category = "observational"


class SourceOp(Op):
    category = "source"


class InterventionalOp(Op):
    category = "interventional"


class CompileOp(Op):
    category = "compile"


class Registry:
    def __init__(self):
        self._ops: dict[str, Type[Op]] = {}

    def register(self, name: str):
        def deco(cls: Type[Op]) -> Type[Op]:
            cls._op_name = name
            self._ops[name] = cls
            return cls
        return deco

    def get(self, name: str) -> Type[Op]:
        if name not in self._ops:
            raise KeyError(f"unknown operator: {name!r} — see `cdj ops` for the zoo")
        return self._ops[name]

    def items(self):
        return sorted(self._ops.items())


OPERATORS = Registry()


def engine_services(ctx: OpContext) -> dict:
    """Build (once) the engine parts interventional ops need."""
    if "replayer" not in ctx.services:
        from causal_data_juicer.replay.replayer import Replayer
        from causal_data_juicer.replay.sandbox import LocalSandbox
        from causal_data_juicer.runtime.collector import Collector
        from causal_data_juicer.runtime.tools import default_registry
        from causal_data_juicer.runtime.verifier import PytestVerifier
        from causal_data_juicer.store.blob import BlobStore

        registry = ctx.services.get("tool_registry") or default_registry()
        verifier = ctx.services.get("verifier") or PytestVerifier()
        blobs = BlobStore(ctx.workdir / "blobs")
        ctx.services.update({
            "tool_registry": registry,
            "verifier": verifier,
            "blobs": blobs,
            "collector": Collector(registry, blobs, verifier),
            "replayer": Replayer(registry, LocalSandbox(blobs, ctx.workdir / "scratch"),
                                 verifier),
        })
    return ctx.services
