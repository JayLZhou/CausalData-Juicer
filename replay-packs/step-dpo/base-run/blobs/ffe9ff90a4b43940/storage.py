import networkx as nx


def save_graph(graph, path):
    nx.write_gpickle(graph, path)


def load_graph(path):
    return nx.read_gpickle(path)
