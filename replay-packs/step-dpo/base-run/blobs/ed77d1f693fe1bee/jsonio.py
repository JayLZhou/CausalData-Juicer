import networkx as nx


def to_json(graph):
    return nx.json_graph.node_link_data(graph)

def from_json(data):
    return nx.json_graph.node_link_graph(data)