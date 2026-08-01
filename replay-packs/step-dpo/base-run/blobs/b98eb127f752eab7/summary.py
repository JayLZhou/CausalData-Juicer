import networkx as nx


def summarize(edges):
    graph = nx.Graph(edges)
    text = nx.info(graph)
    return {'nodes': graph.number_of_nodes(),
            'edges': graph.number_of_edges(),
            'text': text}
