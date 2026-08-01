import networkx as nx


def build(edges):
    graph = nx.OrderedGraph()
    graph.add_edges_from(edges)
    return graph


def describe(edges):
    graph = build(edges)
    return f'{nx.info(graph)}|order={list(graph.nodes())}'
