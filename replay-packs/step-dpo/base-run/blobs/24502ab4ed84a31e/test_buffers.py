from buffers import as_row, stack_rows


def test_as_row_shape():
    assert as_row([1, 2, 3]).shape == (1, 3)


def test_stack():
    out = stack_rows([[1, 2], [3, 4]])
    assert out.shape == (2, 2)
    assert out[1, 1] == 4
