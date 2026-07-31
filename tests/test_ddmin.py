from causal_data_juicer.slicing.ddmin import ddmin


def test_ddmin_single_causal_atom():
    atoms = list(range(8))
    assert ddmin(atoms, lambda s: 5 in s) == [5]


def test_ddmin_pair_of_causal_atoms():
    atoms = list(range(8))
    result = ddmin(atoms, lambda s: 2 in s and 6 in s)
    assert sorted(result) == [2, 6]


def test_ddmin_all_atoms_needed():
    atoms = [0, 1, 2]
    assert ddmin(atoms, lambda s: len(s) == 3) == [0, 1, 2]


def test_ddmin_single_atom_input():
    assert ddmin([7], lambda s: True) == [7]
