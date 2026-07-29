import pytest

from causeforge.interventions.apply import (
    apply_intervention,
    intervention_atoms,
    rebuild_from_atoms,
)
from causeforge.sdk.schemas import (
    ArgEdit,
    Intervention,
    InterventionType,
    LinePatch,
    ToolCall,
)

ORIGINAL = ToolCall(tool="write_file", args={"path": "main.py", "content": "a\nb\nc\n"})


def test_action_replace():
    new = ToolCall(tool="write_file", args={"path": "solution.py", "content": "x\n"})
    iv = Intervention(type=InterventionType.ACTION_REPLACE, target_step=0, new_action=new)
    out = apply_intervention(ORIGINAL, iv)
    assert out.args["path"] == "solution.py"


def test_arg_set_does_not_mutate_original():
    iv = Intervention(
        type=InterventionType.TOOL_ARGUMENT_EDIT,
        target_step=0,
        edits=[ArgEdit(arg="path", op="set", value="solution.py")],
    )
    out = apply_intervention(ORIGINAL, iv)
    assert out.args["path"] == "solution.py"
    assert out.args["content"] == "a\nb\nc\n"
    assert ORIGINAL.args["path"] == "main.py"


def test_patch_lines_preserves_trailing_newline():
    iv = Intervention(
        type=InterventionType.TOOL_ARGUMENT_EDIT,
        target_step=0,
        edits=[ArgEdit(arg="content", op="patch_lines", patches=[LinePatch(line=1, text="B")])],
    )
    out = apply_intervention(ORIGINAL, iv)
    assert out.args["content"] == "a\nB\nc\n"


def test_patch_lines_on_non_string_raises():
    bad = ToolCall(tool="write_file", args={"path": "x", "content": 42})
    iv = Intervention(
        type=InterventionType.TOOL_ARGUMENT_EDIT,
        target_step=0,
        edits=[ArgEdit(arg="content", op="patch_lines", patches=[LinePatch(line=0, text="z")])],
    )
    with pytest.raises(ValueError):
        apply_intervention(bad, iv)


def test_atom_explosion_and_rebuild():
    iv = Intervention(
        type=InterventionType.TOOL_ARGUMENT_EDIT,
        target_step=0,
        edits=[ArgEdit(arg="content", op="patch_lines",
                       patches=[LinePatch(line=0, text="A"), LinePatch(line=2, text="C")])],
    )
    atoms = intervention_atoms(iv)
    assert len(atoms) == 2 and all(len(a.patches) == 1 for a in atoms)
    sub = rebuild_from_atoms(iv, atoms[1:])
    out = apply_intervention(ORIGINAL, sub)
    assert out.args["content"] == "a\nb\nC\n"
