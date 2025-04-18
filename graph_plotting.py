import os
import json
import requests
from bs4 import BeautifulSoup
import networkx as nx
import numpy as np
import random
import packcircles as pc
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator


def multi_component_graph(G, layout="kamada_kawai", r_fraction=1.0, padding=2, min_component_size=1, **layout_params):
    subG_list = [] # list of subcomponents
    pos_subG_list = [] # list of subcomponent positions
    r_list = [] # list of subcomponent radii

    # get components
    if isinstance(G, nx.DiGraph):
        components = nx.weakly_connected_components(G)
    else:
        components = nx.connected_components(G)

    # loop through each connected component
    for component in components:
        if len(component) >= min_component_size:
            # determine subgraph and apply kamada kawai position layout
            subG = G.subgraph(component)
            if layout == "kamada_kawai":
                pos_subG = nx.kamada_kawai_layout(subG, center=(0,0), **layout_params)
            elif layout == "spring":
                pos_subG = nx.spring_layout(subG, center=(0,0), **layout_params)
            elif layout == "spiral":
                pos_subG = nx.spiral_layout(subG, center=(0,0), **layout_params)
            elif layout == "spectral":
                pos_subG = nx.spectral_layout(subG, center=(0,0), **layout_params)
            elif layout == "forceatlas2":
                pos_kk = nx.kamada_kawai_layout(subG, center=(0,0))
                pos_subG = nx.forceatlas2_layout(subG, pos=pos_kk, **layout_params)
                center = np.mean(np.array(list(pos_subG.values())), axis=0)
                pos_subG = {k:v-center for k,v in pos_subG.items()}
            elif layout == "bfs":
                max_deg_node = max(subG.degree, key=lambda x: x[1])[0]
                pos_subG = nx.bfs_layout(subG.to_undirected(), start=max_deg_node, center=(0,0))
            elif layout == "arf":
                pos_subG = nx.arf_layout(subG, **layout_params)
                center = np.mean(np.array(list(pos_subG.values())), axis=0)
                pos_subG = {k:v-center for k,v in pos_subG.items()}
            else:
                raise ValueError(f"{layout} not a recognized layout")
    
            # compute e_lens
            e_lens = []
            for u, v in subG.edges():
                e_len = np.linalg.norm(pos_subG[u] - pos_subG[v])
                e_lens.append(e_len)
            min_e_len = np.min(e_lens)
            max_e_len = np.max(e_lens)
            pos_subG_rescale = {k: v/min_e_len for k, v in pos_subG.items()}
    
            # record positions and subgraphs
            subG_list.append(subG)
            pos_subG_list.append(pos_subG_rescale)
    
            # compute max node distance from center (to determine radius)
            pos_subG_arr = np.array(list(pos_subG_rescale.values()))
            max_r = np.max(np.linalg.norm(pos_subG_arr, axis=1))
            r_list.append(max_r + padding)

    # perform circle packing for circles associated with each component
    r_list_argsort = np.argsort(r_list)
    circle_locs = list(pc.pack([r_fraction*r_list[idx] for idx in r_list_argsort]))
    center = np.array(circle_locs[0][:2])

    # update positions, centering each component at its associated circle location
    pos_subG_rescale_shift = {}
    for idx, (x, y, r) in zip(r_list_argsort, circle_locs):
        for k, v in pos_subG_list[idx].items():
            pos_subG_rescale_shift[k] = v + np.array([x,y])  - center

    return pos_subG_rescale_shift