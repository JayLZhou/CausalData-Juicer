import networkx as nx


def cache_report(edges, cache_path):
    graph = nx.Graph(edges)
    nx.write_graphml(graph, cache_path)
    return str(graph.nodes(data=True))


def cached_degree(cache_path, node):
    graph = nx.read_graphml(cache_path)
    return graph.degree(node)