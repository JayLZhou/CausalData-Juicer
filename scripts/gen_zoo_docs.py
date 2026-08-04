#!/usr/bin/env python3
"""Regenerate the shipped-operator table in docs/operator-zoo.md.

The table is generated from the registry, and a test asserts the file on
disk matches what this script would write — so the documented zoo can
never again advertise more operators than the package actually ships.

    python scripts/gen_zoo_docs.py           # rewrite the section
    python scripts/gen_zoo_docs.py --check   # exit 1 if it is stale
"""

from __future__ import annotations

import sys
from pathlib import Path

import causal_data_juicer.ops  # noqa: F401  (registers every operator)
from causal_data_juicer.ops.base_op import OPERATORS

DOC = Path(__file__).resolve().parent.parent / "docs" / "operator-zoo.md"
BEGIN = "<!-- BEGIN GENERATED ZOO -->"
END = "<!-- END GENERATED ZOO -->"

CATEGORY_BLURB = {
    "observational": "no environment, zero budget — can never raise a tier",
    "source": "propose interventions (model cost, no execution)",
    "interventional": "execute the environment, spend budget, raise tiers",
    "compile": "materialize views; tier-preserving",
}


def _first_sentence(cls: type) -> str:
    doc = " ".join((cls.__doc__ or "").split())
    head = doc.split(". Params")[0].split("Params:")[0].strip().rstrip(".")
    return head or "(undocumented)"


def _params(cls: type) -> str:
    doc = " ".join((cls.__doc__ or "").split())
    if "Params:" not in doc:
        return "—"
    tail = doc.split("Params:", 1)[1].strip().rstrip(".")
    return f"`{tail}`" if tail and tail != "none" else "—"


def render() -> str:
    by_cat: dict[str, list[tuple[str, type]]] = {}
    for name, cls in OPERATORS.items():
        by_cat.setdefault(cls.category, []).append((name, cls))
    total = sum(len(v) for v in by_cat.values())
    out = [
        BEGIN,
        "",
        (
            f"**{total} operators ship in this package**, in the four categories of "
            "the algebra. This table is generated from the registry by "
            "`scripts/gen_zoo_docs.py`; a test fails if it drifts from what "
            "`cdj ops` lists."
        ),
        "",
    ]
    for cat in ("observational", "source", "interventional", "compile"):
        ops = sorted(by_cat.get(cat, []))
        if not ops:
            continue
        out += [
            f"### `{cat}` — {CATEGORY_BLURB[cat]} ({len(ops)})",
            "",
            "| operator | what it does | params |",
            "|---|---|---|",
        ]
        out += [f"| `{name}` | {_first_sentence(cls)} | {_params(cls)} |" for name, cls in ops]
        out.append("")
    out.append(END)
    return "\n".join(out)


def main() -> int:
    text = DOC.read_text()
    if BEGIN not in text or END not in text:
        print(f"{DOC} is missing the {BEGIN} / {END} markers", file=sys.stderr)
        return 2
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    new = head + render() + tail
    if "--check" in sys.argv:
        if new != text:
            print("docs/operator-zoo.md is stale — run scripts/gen_zoo_docs.py", file=sys.stderr)
            return 1
        print("operator zoo docs are in sync with the registry")
        return 0
    DOC.write_text(new)
    print(f"wrote {DOC} ({len(OPERATORS.items())} operators)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
