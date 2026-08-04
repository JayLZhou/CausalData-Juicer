"""CausalData-Juicer: a budgeted interventional data engine for agent improvement."""

from causal_data_juicer.sdk.schemas import (  # noqa: F401
    CausalUnit,
    CostLedger,
    Episode,
    EvidenceTier,
    Intervention,
    InterventionType,
    Outcome,
    SideEffectClass,
    Snapshot,
    Step,
    ToolCall,
)

try:  # single source of truth: pyproject [project].version
    from importlib.metadata import version as _v

    __version__ = _v("causal-data-juicer")
except ImportError:  # pragma: no cover — uninstalled source tree
    __version__ = "0+unknown"
