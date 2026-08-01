from checks import all_positive
from rounding import clip_upper, round2


def test_all_positive():
    assert all_positive([1, 2, 3])
    assert not all_positive([1, -2])


def test_round2():
    assert round2([1.234, 5.678]) == [1.23, 5.68]


def test_clip_default_unbounded():
    assert clip_upper([1.0, 99.0]) == [1.0, 99.0]
