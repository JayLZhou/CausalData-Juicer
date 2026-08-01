import networkx as nx


def summarize(edges):
    graph = nx.Graph()
    graph.add_edges_from(edges)
    return {'nodes': graph.number_of_nodes(),
            'edges': graph.number_of_edges(),
            'text': nx.info(graph)}
