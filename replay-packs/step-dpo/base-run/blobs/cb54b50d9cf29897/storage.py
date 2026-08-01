import networkx as nx


def save_graph(graph, path):
    nx.write_graphml(graph, path)

def load_graph(path):
    return nx.read_graphml(path)