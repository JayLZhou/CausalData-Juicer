import networkx as nx

from storage import load_graph, save_graph


def test_roundtrip(tmp_path):
    graph = nx.path_graph(4)
    target = tmp_path / 'g.gpickle'
    save_graph(graph, target)
    loaded = load_graph(target)
    assert sorted(loaded.edges()) == sorted(graph.edges())
