import networkx as nx


def dag_from_pairs(pairs):
    graph = nx.DiGraph()
    graph.add_edges_from(pairs)
    return graph
