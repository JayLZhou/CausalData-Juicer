from pipeline import build, describe


def test_insertion_order_kept():
    graph = build([(3, 1), (1, 2)])
    assert list(graph.nodes()) == [3, 1, 2]


def test_describe():
    out = describe([(1, 2)])
    assert 'order=[1, 2]' in out
