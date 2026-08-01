import networkx as nx


def to_json(graph):
    return nx.jit_data(graph)


def from_json(data):
    return nx.jit_graph(data)
