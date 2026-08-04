"""Applying interventions to recorded actions.

M1 ships two intervention types:

- ``ACTION_REPLACE``: swap the entire tool call at the target step.
- ``TOOL_ARGUMENT_EDIT``: keep the tool, patch its arguments.  Edits are
  decomposable — an ``ArgEdit`` may be a whole-value ``set`` or a list of
  per-line ``patch_lines`` — and those atoms are what causal slicing
  minimizes over.
"""

from __future__ import annotations

import copy

from causal_data_juicer.sdk.schemas import (
    ArgEdit,
    Intervention,
    InterventionType,
    ToolCall,
)


def apply_arg_edit(args: dict, edit: ArgEdit) -> dict:
    args = copy.deepcopy(args)
    if edit.op == "set":
        args[edit.arg] = edit.value
    elif edit.op == "patch_lines":
        original = args.get(edit.arg)
        if not isinstance(original, str):
            raise ValueError(
                f"patch_lines needs a string arg, got {type(original)} for {edit.arg!r}"
            )
        lines = original.splitlines()
        for patch in edit.patches:
            if patch.line >= len(lines):
                lines.extend([""] * (patch.line - len(lines) + 1))
            lines[patch.line] = patch.text
        args[edit.arg] = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
    else:
        raise ValueError(f"unknown edit op: {edit.op}")
    return args


def apply_intervention(original: ToolCall, intervention: Intervention) -> ToolCall:
    if intervention.type == InterventionType.ACTION_REPLACE:
        if intervention.new_action is None:
            raise ValueError("ACTION_REPLACE requires new_action")
        return intervention.new_action.model_copy(deep=True)
    if intervention.type == InterventionType.TOOL_ARGUMENT_EDIT:
        args = original.args
        for edit in intervention.edits:
            args = apply_arg_edit(args, edit)
        return ToolCall(tool=original.tool, args=args)
    raise ValueError(f"unknown intervention type: {intervention.type}")


# --- decomposition into atoms for causal slicing ---------------------------


def intervention_atoms(intervention: Intervention) -> list[ArgEdit]:
    """Explode a TOOL_ARGUMENT_EDIT into its finest-grained atoms.
    ACTION_REPLACE is atomic (returns [])."""
    atoms: list[ArgEdit] = []
    for edit in intervention.edits:
        if edit.op == "patch_lines" and len(edit.patches) > 1:
            atoms.extend(ArgEdit(arg=edit.arg, op="patch_lines", patches=[p]) for p in edit.patches)
        else:
            atoms.append(edit)
    return atoms


def rebuild_from_atoms(intervention: Intervention, atoms: list[ArgEdit]) -> Intervention:
    sub = intervention.model_copy(deep=True)
    sub.edits = [a.model_copy(deep=True) for a in atoms]
    return sub
