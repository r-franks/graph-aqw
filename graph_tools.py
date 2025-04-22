import networkx as nx

##################################################################################################
################################# GRAPH UTILITY FUNCTIONS ########################################
##################################################################################################
def try_remove_edge(G, a, b):
    try:
        G.remove_edge(a, b)
        return None
    except nx.NetworkXError:
        return None


def remove_unreciprocated_nodes(G, nodes):
    G = G.copy()
    for target in nodes:
        # find nodes that point to target
        incoming = list(G.predecessors(target))
        for predecessor in incoming:
            # remove edge if it isn't reciprocated
            if not G.has_edge(target, predecessor):
                G.remove_edge(predecessor, target)

    # remove isolated nodes
    isolated_nodes = list(nx.isolates(G))
    G.remove_nodes_from(isolated_nodes)
    return G


def assign_by_neighbor(G, node_to_value_dict):
    node_to_value_dict = node_to_value_dict.copy()
    uncategorized_nodes = set(G.nodes()) - set(node_to_value_dict.keys())
    indeterminate_nodes = set()

    # handle components that have no value at any node
    components = [c for c in nx.connected_components(G)]
    for c in components:
        any_value = False
        for node in c:
            if node_to_value_dict.get(node, None) is not None:
                any_value = True
                break
        if not any_value:
            c_set = set(c)
            indeterminate_nodes = indeterminate_nodes.union(c_set)
            uncategorized_nodes = uncategorized_nodes - c_set

    node_to_value_dict_prog = 0
    while len(node_to_value_dict) > node_to_value_dict_prog:
        node_to_value_dict_prog = len(node_to_value_dict)
        for node in uncategorized_nodes:
            possible_values = set()
            for neighbor in G.neighbors(node):
                possible_value = node_to_value_dict.get(neighbor, None)
                if possible_value is not None:
                    possible_values.add(possible_value)
            if len(possible_values) == 0:
                pass
            elif len(possible_values) == 1:
                node_to_value_dict[node] = list(possible_values)[0]
                uncategorized_nodes = uncategorized_nodes - {node}
            else:
                uncategorized_nodes = uncategorized_nodes - {node}
        n_uncategorized_nodes_prev = len(uncategorized_nodes)
    return node_to_value_dict