import os
import json
import requests
from bs4 import BeautifulSoup
import networkx as nx
import numpy as np
import random
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from urllib.parse import urljoin
import time

from aqw_region_pull import get_region_to_loc_dict
from graph_plotting import multi_component_graph
from graph_tools import remove_unreciprocated_nodes, try_remove_edge, assign_by_neighbor


##################################################################################################
############################ DEFINE INVALID VALID ROOM CONNECTIONS ###############################
##################################################################################################
# terms that make the access point likely to be geographic
geo_terms = ["north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"]
prepositions = ["of", "at"]

geo_phrases = []
# mobius<=cornelis (aqwwiki.wikidot.com/mobius)
geo_phrases.append("of screen")
# towerofdoom6<=towerofdoom7 (http://aqwwiki.wikidot.com/tower-of-doom-6)
geo_phrases.append("stairs")
# general direction terms
for geoterm in geo_terms:
    for preposition in prepositions:
        geo_phrases.append(f"{geoterm} {preposition}")

# terms that make the accesss point unlikely to be geographic
non_geo_phrases = ["join", "talk", "button", "map", "event hub", "statue"]
def is_access_geographic(s):
    # not geographic, return false
    # (typically if there's a hyperlink but no explanation of connection)
    if len(s) == 0:
        return False

    # reject one-word lines
    # (see aqwwiki.wikidot.com/escherion-s-tower)
    if len(s.split(" ")) <= 1:
        return False

    s_lower = s.lower()

    non_geo_flag = 0
    geo_flag = 0

    for phrase in geo_phrases:
        if phrase in s_lower:
            geo_flag += 1

    # non geo takes precedence
    # no geo phrases but a non-geo phrase implies non-geo
    for phrase in non_geo_phrases:
        # be careful of multiple inline access methods (e.g. http://aqwwiki.wikidot.com/mobius)
        if phrase in s_lower:
            non_geo_flag += 1

    if geo_flag >= non_geo_flag:
        return True
    else:
        return False


# loop to handle cases when an access point may connect to a room in
# multiple ways
def is_loc_geographic(s):
    s_split = [t for t in s.split("\n") if len(t)>0]
    if len(s_split) == 1:
        return is_access_geographic(s_split[0])
    else:
        for s_line in s_split:
            if is_access_geographic(s_line):
                return True
        return False


##################################################################################################
########################################## WIKI SCRAPE ###########################################
##################################################################################################
# base url for wiki
BASE_URL = "http://aqwwiki.wikidot.com/"
def get_connected_rooms(map_extension, return_map_name=True, return_permanence=True, condition=None, sleep_duration=1):
    if condition is None:
        condition = lambda x: True

    # sleep to avoid overwhelming server
    time.sleep(sleep_duration)

    # scrape html and get page-content
    url = f"{BASE_URL}/{map_extension}"
    res = requests.get(url)
    map_site = BeautifulSoup(res.text, "html.parser")
    map_site_content = map_site.find("div", id="page-content")

    try:
        # verify that map_extension is a location
        is_location = "location" in map_site.find("div", {"class": "page-tags"}).get_text()
    except AttributeError:
        # if this fails, then the request failed, wait and try again
        time.sleep(sleep_duration)
        res = requests.get(url)
        map_site = BeautifulSoup(res.text, "html.parser")
        map_site_content = map_site.find("div", id="page-content")
        # if it fails again raise an error and print the map extension
        try:
            is_location = "location" in map_site.find("div", {"class": "page-tags"}).get_text()
        except:
            print(f"{map_extension} text issue")
            return None

    # handle case where link is not to a location
    if not is_location:
        # no access points if not a location
        hrefs = []
        outputs = [hrefs]
        if return_map_name:
            # name based purely on map extension (+ N/A to flag it as not a location)
            outputs.append(f"{map_extension}: N/A")
        if return_permanence:
            # we can still check its seasonality, technically (but it doesn't mean the same thing)
            is_seasonal = "seasonal" in map_site.find("div", {"class": "page-tags"}).get_text()
            is_rare = "rare" in map_site.find("div", {"class": "page-tags"}).get_text()
            is_permanent = is_seasonal == False and is_rare == False
            outputs.append(is_permanent)
        # return outputs without further processing
        return outputs

    # if it is a location, find the "access points" header which precedes a list of access points
    access_header = map_site_content.find("strong", string=lambda s: s and "access points" in s.lower())
    # get its parent
    access_header_parent = access_header.parent
    # get all text of parent
    extra_text_in_header = access_header_parent.get_text().lower().split("access points")[-1]

    # check if there's significant text in the header after "access points" are mentioned
    if len(extra_text_in_header) > 4:
        # we assume in this case that access points are included inline with the header
        # we assume this will be something like "/join map_name", not a meaningful access point
        extra_text_in_header.strip(":").strip()
        hrefs = []
        outputs = [hrefs]
        if return_map_name:
            # determine map name
            map_name_text = map_site.find("strong", string=lambda s: s and "map name" in s.lower())
            map_name = map_name_text.next_sibling.strip()
            outputs.append(map_name)
        if return_permanence:
            # determine seasonality
            is_seasonal = "seasonal" in map_site.find("div", {"class": "page-tags"}).get_text()
            is_rare = "rare" in map_site.find("div", {"class": "page-tags"}).get_text()
            is_permanent = is_seasonal == False and is_rare == False
            outputs.append(is_permanent)
        return outputs

    # get sibling following the "access points" header parent
    # this will contain the list of access points if they weren't in the header
    access_list = access_header_parent.find_next_sibling()

    # check if next sibling is None
    tries = 0
    while access_list is None and tries < 5:
        access_header_parent = access_header_parent.parent
        if access_header_parent is None:
            break
        else:
            access_list = access_header_parent.find_next_sibling()
            tries +=1

    # check if next sibling is a div
    if access_list.name == "div":
        # if it is, access points are likely in collapsible content
        # we descend structure to find the contained ul / list
        access_list = access_list.find("div", {"class": "collapsible-block-unfolded"})
        access_list = access_list.find("div", {"class": "collapsible-block-content"})
        access_list = access_list.find("ul")

    # otherwise, we assume the next sibling is the ul / list of access points itself
    access_list_cond = []
    # loop through li elements, get text, and check if it satisfies the condition
    for a in access_list.find_all("li", recursive=False):
        # strip links
        # non_link_text = ''.join(item.get_text() for item in a.contents if not item.name == 'a').strip()
        # if condition(non_link_text):
        #     access_list_cond.append(a)
        if condition(a.get_text()):
            access_list_cond.append(a)

    # find all links in the list of access point and record them all
    hrefs = []
    for a in access_list_cond:
        for link in a.find_all("a", href=True, recursive=False):
            link_href = link["href"].strip("/")
            if not "." in link_href:
                hrefs.append(link_href)

    # add links to outputs
    outputs = [hrefs]

    # determine map name
    if return_map_name:
        map_name_text = map_site.find("strong", string=lambda s: s and "map name" in s.lower())
        map_name = map_name_text.next_sibling.get_text().strip()
        if len(map_name) == 0:
            map_name = f"/{map_extension}"
        outputs.append(map_name)

    # determine permanence (based on seasonality, rarity of room) of room
    if return_permanence:
        is_seasonal = "seasonal" in map_site.find("div", {"class": "page-tags"}).get_text()
        is_rare = "rare" in map_site.find("div", {"class": "page-tags"}).get_text()
        is_permanent = is_seasonal == False and is_rare == False
        outputs.append(is_permanent)

    # return outputs
    return outputs


##################################################################################################
################################## RECURSIVE WIKI CRAWL ##########################################
##################################################################################################
def aqw_wiki_crawl(starting_rooms, degree = 16, pursue_impermanent=False, condition="none", sleep_duration = 1, verbose=2):
    if condition == "none":
        condition_func = None
    elif condition == "geo":
        condition_func = is_loc_geographic

    # time the crawl
    start = time.time()
    
    # instantiate global variables
    visited = set()
    link_to_name_dict = {}
    link_to_permanence_dict = {}
    G = nx.DiGraph()
    query_counter = [0]

    # define recursive function
    # (recursively traverses all access points to a room)
    def expand_graph(room, degree, pursue_impermanent=False, sleep_duration=1, verbose=2):
        # retrieve access points, room name
        result = get_connected_rooms(room, 
                                     return_map_name=True, 
                                     return_permanence=True,
                                     condition=condition_func,
                                     sleep_duration=sleep_duration)
        if result is None:
            return None
        else:
            access_points, map_name, is_permanent = result

        query_counter[0] = query_counter[0] + 1
    
        # update room info
        visited.add(room)
        link_to_name_dict[room] = map_name
        link_to_permanence_dict[room] = is_permanent

        # if the access point is permanent or we pursue impermanent access points...
        if is_permanent or pursue_impermanent:
            # add room access points to graph
            for access_point in access_points:
                G.add_edge(access_point, room)

            # filter access points to those we haven't visited
            new_rooms = set(access_points) - visited
            # if new rooms exist and degree > 0, traverse access points of each new room
            if degree > 0 and len(new_rooms) > 0:
                for new_room in new_rooms:
                    if verbose > 1:
                        print(f"[{len(visited)}] {str(room)}<={new_room}")
                    expand_graph(new_room, 
                                 degree = degree - 1, 
                                 pursue_impermanent=pursue_impermanent,
                                 sleep_duration=sleep_duration,
                                 verbose=verbose)
        return None

    non_location_links = ["game-menu", "maps"]
    for starting_room in starting_rooms:
        if starting_room not in visited and not starting_room in non_location_links:
            # run recursive function
            expand_graph(starting_room, 
                         degree=degree, 
                         pursue_impermanent=pursue_impermanent, 
                         sleep_duration=sleep_duration,
                         verbose=verbose)

    end = time.time()
    crawl_time = end - start
    if verbose > 0:
        print(f"{query_counter[0]} webpages crawled.")
        print(f"Crawl of degree {degree} complete in {crawl_time} seconds.")

    # add links missed on the WiKi
    G.add_edge("mobius", "greenguard-west")
    G.add_edge("greenguard-west", "mobius")

    G.add_edge("tower-of-doom-6", "tower-of-doom-1")
    G.add_edge("tower-of-doom-1", "tower-of-doom-6")

    G.add_edge("queen-iona-challenge-fight", "castle-gaheris")
    G.add_edge("castle-gaheris", "queen-iona-challenge-fight")

    G.add_edge("queen-iona-challenge-fight", "castle-gaheris")
    G.add_edge("castle-gaheris", "queen-iona-challenge-fight")

    G.add_edge("queen-iona-challenge-fight", "castle-gaheris")

    G.add_edge("portal-location", "swordhaven-bridge")
    G.add_edge("balemorale-castle", "termina-temple")

    G.add_edge("djinn-gate", "oasis")

    try_remove_edge(G, "cleric", "akiba")
    try_remove_edge(G, "akiba", "cleric")

    try_remove_edge(G, "akiba", "skytower-aegis")
    try_remove_edge(G, "skytower-aegis", "akiba")

    try_remove_edge(G, "akiba", "beleen-s-dream")
    try_remove_edge(G, "beleen-s-dream", "akiba")

    try_remove_edge(G, "akiba", "cave-of-wanders")
    try_remove_edge(G, "cave-of-wanders", "akiba")

    try_remove_edge(G, "akiba", "librarium")
    try_remove_edge(G, "librarium", "akiba")

    try_remove_edge(G, "akiba", "skytower-aegis")
    try_remove_edge(G, "skytower-aegis", "akiba")

    try_remove_edge(G, "akiba", "vasalkar-s-lair")
    try_remove_edge(G, "vasalkar-s-lair", "akiba")

    try_remove_edge(G, "akiba", "yokai-river")
    try_remove_edge(G, "yokai-river", "akiba")

    try_remove_edge(G, "akiba", "yokai-star-river")
    try_remove_edge(G, "yokai-star-river", "akiba")

    try_remove_edge(G, "battleon", "grimskull-annex")

    crawl_params = {"starting_rooms": starting_rooms,
                    "degree": degree,
                    "pursue_impermanent": pursue_impermanent,
                    "condition": condition,
                    "sleep_duration": sleep_duration,
                    "verbose": verbose}
    output_dict = {"crawl_params": crawl_params,
                   "crawl_time": crawl_time,
                   "requests": query_counter[0],
                   "link_to_name_dict": link_to_name_dict,
                   "link_to_permanence_dict": link_to_permanence_dict,
                   "DiGraph": G}
    return output_dict


# saves crawl outputs
def save_crawl_outputs(crawl_outputs, loc="crawl_data.json"):
    crawl_params = crawl_outputs["crawl_params"]
    crawl_time = crawl_outputs["crawl_time"]
    query_counter = crawl_outputs["requests"]
    link_to_name_dict = crawl_outputs["link_to_name_dict"]
    link_to_permanence_dict = crawl_outputs["link_to_permanence_dict"]
    G = crawl_outputs["DiGraph"]

    crawl_output_json = {}
    crawl_output_json["crawl_params"] = crawl_params
    crawl_output_json["crawl_time"] = crawl_time
    crawl_output_json["requests"] = query_counter
    crawl_output_json["link_to_name_dict"] = link_to_name_dict.copy()
    crawl_output_json["link_to_permanence_dict"] = link_to_permanence_dict.copy()
    crawl_output_json["DiGraph_Raw"] = nx.node_link_data(G)

    # process digraph
    # remove non-permanent rooms, relabel nodes to correspond to names rather than wiki extensions
    perm_links = {link for link, permanence in link_to_permanence_dict.items() if permanence}
    G_perm = G.subgraph(perm_links).copy()
    G_perm_relabel = nx.relabel_nodes(G_perm, link_to_name_dict)
    # remove links that have "N/A" in them, signifying that they aren't locations
    loc_links = [loc for loc in list(G_perm_relabel.nodes()) if "N/A" not in loc]
    G_perm_relabel = G_perm_relabel.subgraph(loc_links).copy()
    crawl_output_json["DiGraph_Proc"] = nx.node_link_data(G_perm_relabel)

    # get undirected graph, keeping only reciprocated edges
    edges_to_keep = [(u, v) for u, v in G_perm_relabel.edges() if G_perm_relabel.has_edge(v, u)]
    G_perm_relabel_undir = nx.DiGraph()
    G_perm_relabel_undir.add_edges_from(edges_to_keep)
    G_perm_relabel_undir = G_perm_relabel_undir.to_undirected()
    crawl_output_json["Graph_Undir"] = nx.node_link_data(G_perm_relabel_undir)  # convert to serializable format

    # save outputs
    with open(loc, "w") as f:
        json.dump(crawl_output_json, f, indent=4)


def plot_crawl_outputs(crawl_outputs, 
                       region_color_map, 
                       region_to_loc_map, 
                       save_loc="", **kwargs):
    region_color_map = region_color_map.copy()
    region_to_loc_map = region_to_loc_map.copy()
    
    crawl_params = crawl_outputs["crawl_params"]
    crawl_time = crawl_outputs["crawl_time"]
    query_counter = crawl_outputs["requests"]
    link_to_name_dict = crawl_outputs["link_to_name_dict"]
    link_to_permanence_dict = crawl_outputs["link_to_permanence_dict"]

    Graph_Undir = nx.node_link_graph(crawl_outputs["Graph_Undir"], directed=False)
    DiGraph_Raw = nx.node_link_graph(crawl_outputs["DiGraph_Raw"], directed=True)
    DiGraph_Proc = nx.node_link_graph(crawl_outputs["DiGraph_Proc"], directed=True)
    all_nodes = set(list(DiGraph_Raw.nodes()))

    # filter out connections to hub nodes
    hub_nodes = ["battleon", "battleontown", "castle"]
    DiGraph_Proc_filt = remove_unreciprocated_nodes(DiGraph_Proc, hub_nodes)

    # remap to locations
    region_to_loc_map_filt = {}
    for k, v in region_to_loc_map.items():
        region_to_loc_map_filt[k] = []
        for loc in v:
            if loc in link_to_name_dict:
                region_to_loc_map_filt[k].append(link_to_name_dict[loc])
    
    # determine number of locations in each region
    locs_by_region = [(k, len(v)) for k,v in region_to_loc_map_filt.items()]
    locs_by_region = sorted(locs_by_region, key=lambda x: x[1])
    
    # associate locations with specific regions
    # we go from smaller to larger regions, so locations are
    # assigned to the largest region their tied to
    loc_to_region_map = {}
    for region, _ in locs_by_region:
        for loc in region_to_loc_map_filt[region]:
            loc_to_region_map[loc] = region

    # assign regions to colors
    loc_to_region_map = assign_by_neighbor(Graph_Undir, loc_to_region_map)
    loc_to_region_map = assign_by_neighbor(DiGraph_Proc_filt.to_undirected(), loc_to_region_map)
    
    for node in set(Graph_Undir.nodes()) - set(loc_to_region_map.keys()):
        loc_to_region_map[node] = "Unknown"
    
    loc_to_color_map = {k: region_color_map.get(v, "lightblue") for k, v in loc_to_region_map.items()}

    # plot undirected graph
    #################################################################################
    pos = multi_component_graph(Graph_Undir, **kwargs)
    fig, ax = plt.subplots(figsize=[48, 32])
    G = Graph_Undir.subgraph(pos.keys())
    nx.draw(G, 
            pos, 
            with_labels=True, 
            node_size=1000, 
            node_color=[loc_to_color_map[node] for node in G.nodes()], 
            ax=ax)
    fig.tight_layout()
    # fig.savefig(f"{save_loc}/aqw_graph_undir.png", dpi=300)
    fig.savefig(f"{save_loc}/aqw_graph_undir.svg")

    # plot directed graph (unprocessed)
    #################################################################################
    pos = multi_component_graph(DiGraph_Proc, **kwargs)
    fig, ax = plt.subplots(figsize=[48, 32])
    G = DiGraph_Proc.subgraph(pos.keys())
    nx.draw(G, 
            pos, 
            with_labels=True, 
            node_size=1000, 
            node_color=[loc_to_color_map.get(node, "lightblue") for node in G.nodes()], 
            ax=ax)
    fig.tight_layout()
    # fig.savefig(f"{save_loc}/aqw_graph_dir_raw.png", dpi=300)
    fig.savefig(f"{save_loc}/aqw_graph_dir_raw.svg")

    # plot directed graph (filtered)
    #################################################################################
    pos = multi_component_graph(DiGraph_Proc_filt, **kwargs)
    fig, ax = plt.subplots(figsize=[48, 32])
    G = DiGraph_Proc_filt.subgraph(pos.keys())
    nx.draw(G, 
            pos, 
            with_labels=True, 
            node_size=1000, 
            arrows=True,
            node_color=[loc_to_color_map.get(node, "lightblue") for node in G.nodes()], 
            ax=ax)
    fig.tight_layout()
    # fig.savefig(f"{save_loc}/aqw_graph_dir_filt.png", dpi=300)
    fig.savefig(f"{save_loc}/aqw_graph_dir_filt.svg")

    # plot undirected graph size as fxn of degree
    #################################################################################
    max_degree_room = max(DiGraph_Proc.degree, key=lambda x: x[1])[0]

    # plot num nodes vs degree
    fig, ax = plt.subplots(figsize=[48, 32])
    nodes_from_start = []
    degree = crawl_params["degree"]
    diameters = [nx.diameter(DiGraph_Proc.subgraph(c).to_undirected()) for c in nx.weakly_connected_components(DiGraph_Proc)]
    for k in range(max(diameters)+1):
        nodes_within_k = nx.single_source_shortest_path_length(DiGraph_Proc, max_degree_room, cutoff=k).keys()
        nodes_from_start.append(len(nodes_within_k))    
    ax.plot(nodes_from_start, 'o-')
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel(f"Degrees from {max_degree_room}")
    ax.set_ylabel("Locations")
    fig.tight_layout()
    # fig.savefig(f"{save_loc}/aqw_nodes_degree.png", dpi=300)
    fig.savefig(f"{save_loc}/aqw_nodes_degree.svg", dpi=300)


##################################################################################################
######################################## MAIN FUNCTION ###########################################
##################################################################################################
def main():
    degree = np.inf
    pursue_impermanent = False
    condition = "geo" # "geo" "none"
    sleep_duration = 1
    verbose = 2

    region_list_url = "http://aqwwiki.wikidot.com/locations"
    working_directory = os.getcwd()
    color_map_loc = f"{working_directory}/region_color_map.json"
    region_map_loc = f"{working_directory}/region_map.json"

    os.makedirs(f"{working_directory}/{condition}", exist_ok=True)
    crawl_output_loc = f"{working_directory}/{condition}/crawl_data.json"

    # determine which regions contain which locations
    region_to_loc_dict = get_region_to_loc_dict(region_url=region_list_url)
    with open(f"{working_directory}/region_map.json", "w") as f:
        json.dump(region_to_loc_dict, f, indent=4)

    # pick a starting room in each non-empty region
    starting_rooms = [v for k in region_to_loc_dict.keys() for v in region_to_loc_dict[k]]
    starting_rooms = list(set(starting_rooms))

    # perform crawl and save results
    crawl_outputs = aqw_wiki_crawl(starting_rooms, 
                                   degree=degree, 
                                   pursue_impermanent=pursue_impermanent,
                                   condition = condition,
                                   sleep_duration=sleep_duration, 
                                   verbose=2)
    save_crawl_outputs(crawl_outputs, loc=crawl_output_loc)

    with open(crawl_output_loc, "r") as f:
        crawl_outputs = json.load(f)
    with open(color_map_loc, "r") as f:
        color_map = json.load(f)
    with open(region_map_loc, "r") as f:
        region_map = json.load(f)
    plot_crawl_outputs(crawl_outputs, 
                       color_map, 
                       region_map, 
                       save_loc=f"{working_directory}/{condition}",
                       layout="forceatlas2",
                       r_fraction=0.9, 
                       min_component_size=3, 
                       strong_gravity=True,
                       max_iter=1000
                      )
    # plot_crawl_outputs(crawl_outputs, 
    #                    color_map, 
    #                    region_map, 
    #                    save_loc=f"{working_directory}/{condition}",
    #                    layout="bfs",
    #                    r_fraction=0.7, 
    #                    min_component_size=3, 
    #                   )


if __name__ == "__main__":
    main()