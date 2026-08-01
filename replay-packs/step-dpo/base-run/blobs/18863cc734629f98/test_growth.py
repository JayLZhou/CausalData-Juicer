from growth import compound


def test_compound():
    assert compound([2.0, 3.0, 0.5]) == [2.0, 6.0, 3.0]


def test_single():
    assert compound([5]) == [5]
