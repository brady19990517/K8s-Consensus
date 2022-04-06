import math
import numpy as np
import networkx as nx

#Currently assume all graph created is digraph
def gen_graph(nodes:int, show_graph:bool):
    if nodes<1:
        print("Require at least one node")
        return None
    
    max_graph_iter = 100000
    min_graph_diameter = 1
    has_min_diameter = 0
    cnt = 0

    adj = None
    distance = None
    while cnt < max_graph_iter:
        # create the matrix using full zeros
        adj = np.ones((nodes, nodes))
        indices = np.random.choice(nodes*nodes, replace=False, size=int(nodes*nodes*0.85))
        adj[np.unravel_index(indices, adj.shape)] = 0
    
        #Create DiGraph using networkX
        G = nx.DiGraph(adj)
        p = dict(nx.shortest_path_length(G))
        distance=-1
        for d in list(p.values()):
            for i in range(nodes):
                value = math.inf if i not in d else d[i]
                distance = max(distance,value)
        
        if not math.isinf(distance) and distance>=min_graph_diameter:
            has_min_diameter = 1

        #Check if digraph is strongly connected
        #A directed graph is strongly connected if and 
        #only if every vertex in the graph is reachable from every other vertex.
        connecticity_satisfied = nx.is_strongly_connected(G)

        if connecticity_satisfied and has_min_diameter == 1:
            break
        cnt = cnt + 1

    if cnt == max_graph_iter and has_min_diameter == 0:
        print("min graph distance was not satisfied")
        return None
    
    if show_graph:
        nx.draw(G, with_labels=True)
    return adj, distance
