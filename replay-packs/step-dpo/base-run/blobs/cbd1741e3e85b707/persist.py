import networkx as nx

from build_graph import dag_from_pairs


def build_and_save(pairs, path):
    graph = dag_from_pairs(pairs)
    nx.write_gpickle(graph, path)


def load(path):
    return nx.read_gpickle(path)
