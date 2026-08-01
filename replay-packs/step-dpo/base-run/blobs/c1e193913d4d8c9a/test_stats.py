import math

from stats import MISSING, fill_missing, to_float_array


def test_missing_is_nan():
    assert math.isnan(MISSING)


def test_fill_missing():
    assert fill_missing([1.0, MISSING, 3.0]) == [1.0, 0.0, 3.0]


def test_dtype():
    assert to_float_array([1]).dtype.kind == 'f'
