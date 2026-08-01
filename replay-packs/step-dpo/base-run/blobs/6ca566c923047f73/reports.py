import networkx as nx


def cache_report(edges, cache_path):
    graph = nx.Graph(edges)
    nx.write_gpickle(graph, cache_path)
    return nx.info(graph)


def cached_degree(cache_path, node):
    graph = nx.read_gpickle(cache_path)
    return graph.degree(node)
