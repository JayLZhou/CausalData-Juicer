import networkx as nx


def build(edges):
    graph = nx.Graph()
    graph.add_edges_from(edges)
    return graph


def describe(edges):
    graph = build(edges)
    return f'{graph.number_of_nodes()} nodes, {graph.number_of_edges()} edge(s)|order={list(graph.nodes())}'