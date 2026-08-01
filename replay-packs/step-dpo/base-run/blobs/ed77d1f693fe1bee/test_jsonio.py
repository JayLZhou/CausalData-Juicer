import networkx as nx

from jsonio import from_json, to_json


def test_roundtrip():
    graph = nx.Graph([(1, 2), (2, 3)])
    data = to_json(graph)
    loaded = from_json(data)
    assert sorted(loaded.nodes()) == [1, 2, 3]
    assert loaded.number_of_edges() == 2
