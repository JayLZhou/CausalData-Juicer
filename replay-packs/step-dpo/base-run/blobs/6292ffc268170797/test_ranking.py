from ranking import combined_odds, sorted_scores


def test_sorted():
    assert sorted_scores([3, 1, 2]) == [1, 2, 3]


def test_odds():
    assert combined_odds([2.0, 0.5, 3.0]) == 3.0
