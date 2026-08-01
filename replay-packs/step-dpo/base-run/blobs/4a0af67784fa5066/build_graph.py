import networkx as nx


def dag_from_pairs(pairs):
    graph = nx.OrderedDiGraph()
    graph.add_edges_from(pairs)
    return graph
