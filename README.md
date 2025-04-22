# Mapping AdventureQuest Worlds
AdventureQuest Worlds (AQW for short) is a decade-plus old flash game where you fight monsters, travel to new locations, and fight even more monsters. In many cases, these new locations can be walked or quick-travelled to using the world map. However, the fastest and most common method of travel is direct teleportation using the <code>/join location_name</code> text command. With this command, a player need not know how to get to the location physically, or even where the location is on the map. 

As more and more locations have been added (over a thousand!) without commensurate map updates, teleportation by text-command has become a load-bearing feature of AQW -- used both out of necessity and convenience -- and the topography of the world has become easy to forget. In this repository, we seek to remember: to reconstruct the "true" topology of AQW. And all the information we need is on the [AQW Wiki](http://aqwwiki.wikidot.com/).

## Usage
To run the code, simply navigate to the folder where this repository located on your computer and run the code

<code>python aqw_loc_crawl</code>

By default, this code crawls the AQW Wiki and makes note of all connections between locations that are not seasonal or rare. If you would like to filter connections to only those that reflect physicality/geography (see below for details), you may run this code with the <code>condition</code> argument.

<code>python aqw_loc_crawl --condition geo</code>

This argument is the most important. To see others, you may run <code>python aqw_loc_crawl.py -h</code>.

### Outputs
If no condition is applied to filter connections, the results of the script will be placed in the <code>/none</code> sub-directory. Otherwise, they will be placed in the <code>/geo</code> sub-directory. The files contained in these directories include:
* crawl_data.json: A JSON file containing all graph information. Keys include
  * crawl_params: parameters used to run the crawl
  * crawl_time: time taken to perform the Wiki crawl
  * requests: count of total number of requests made to the Wiki
  * link_to_name_dict: maps AQW Wiki extensions to map names
  * link_to_permanence_dict: maps AQW Wiki extensions to whether the locations are permanent (not seasonal or rare)
  * DiGraph_Raw: directed graph using Wiki extensions for node names
  * DiGraph_Proc: directed graph using map names for node names
  * Graph_Undir: undirected graph containing bi-directional connections only

* Visualization files for the graph of bi-directional connections
  * aqw_graph_undir.svg: SVG plot
  * aqw_graph_undir_ct.json: cytoscape information for display on websites
* Visualization files for the directed graph
  * aqw_graph_dir_raw.svg: SVG plot
  * aqw_graph_dir_raw_ct.json: cytoscape information for display on websites
* Visualization files for the directed graph with un-reciprocated connections to hub-towns filtered out
  * aqw_graph_dir_filt.svg: SVG plot
  * aqw_graph_dir_filt_ct.json: cytoscape information for display on websites


## Approach
### Information retrieval approach
Each location page on the AQW Wiki lists all the ways its location can be accessed from other locations, i.e. its "access points." For example, if we see the location <code>battleon-town</code> under the "access points" header on the Wiki page for <code>battleon</code>, we can conclude that there is a connection <code>battleon-town</code>&rarr;<code>battleon</code> which provides information about the topology of AQW. After recording all of the access points, we can further pull-up the Wiki pages for each of those access points in turn and learn <em>their</em> access points. We might learn that there is a connection <code>greenguard-east</code>&rarr;<code>battleon-town</code> which means that <code>greenguard-east</code>&rarr;<code>battleon-town</code>&rarr;<code>battleon</code> is a route that can be used to access <code>battleon</code> from <code>greenguard-east</code>. By repeating this process recursively from some starting location, we can learn about the connections of all locations that might be used to access the starting location. This recursive approach is implemented in the [<code>aqw_wiki_crawl</code>](https://github.com/r-franks/graph-aqw/blob/main/aqw_loc_crawl.py) function.

At the end of this procedure, we are essentially left with a [directed graph](https://en.wikipedia.org/wiki/Directed_graph) of connections (e.g. <code>battleon-town</code>&rarr;<code>battleon</code>) where each location is a node and each pair of a location with its access point is a directed edge pointing from the access point to its location. Analyzing graphs of this sort can tell us how we can get from one location to another location without text-command teleporting and thus help us learn about how locations really connect to each other (either in the putative physical space of the game or in its narrative space). But pulling unstructured information from websites can be tricky.

### Pulling access point information from the AQW Wiki
As mentioned, the list of access points to a particular location in AQW typically follows the <em>Access Points:</em> header and precedes a <em>Notes:</em> (if notes are present) and images showing each screen in the location. However, these access points can b contained:
* in a bulleted list (see [<code>yulgar-s-inn</code>](http://aqwwiki.wikidot.com/yulgar-s-inn))
* in a bulleted list with sub-bullets (see [<code>mobius</code>](http://aqwwiki.wikidot.com/mobius))
* in the <em>Access Points:</em> header itself (see [<code>the-vault-location</code>](https://web.archive.org/web/20241114081324/http://aqwwiki.wikidot.com/the-vault-location))
* in a collapsible <code>div</code> (see [<code>battleon-town</code>](http://aqwwiki.wikidot.com/battleon-town))
* outside of element containing the <em>Access Points:</em> header (see [<code>the-towers</code>](http://aqwwiki.wikidot.com/the-towers))

Our code checks for each of these cases to find the appropriate element containing information on access point lists. Then, we can identify all the links present in the access point list to identify the web-pages associated with each of them. In some cases, these links may not be associated with locations, but rather quests, characters or in-game location maps. These, of course, lack information about access points and should not be included in our analysis. Fortunately, every Wiki page associated with a location has a location tag at the bottom in a <code>page-tags</code> element. Thus, we can treat each link as if it is a location link, navigate to its Wiki page, determine and record whether it is a location, and only attempt to determine access points if it is one.

### Filtering access point information by various conditions
Even when a location in AQW cannot be walked to, many characters and objects provide interactive buttons which automatically teleport a player to a particular location when clicked. When these characters and objects are in a certain location, these locations are present on the Wiki page as access points. Hoever, while such buttons may reveal meaningful narrative connections between locations, they do not necessarily have implications for the geography of AQW. By geography, I mean understanding of when it is possible (or should be possible) to <em>walk</em> from one location to another.

To analyze the geography in particular, we do some basic text analysis to see whether a location is an access point by walking or by some other means. To do this we:
1. Check for flags indicating physical travel
   * Combinations of directions and prepositions, i.e. <em>north of</em>, <em>southwest of</em>
   * Words indicating physical travel, i.e. <em>stairs</em> (see [<code>tower-of-doom-6</code>](http://aqwwiki.wikidot.com/tower-of-doom-6))
   * The phrase <em>of screen</em>, which is typically preceded by a direction
2. Check for flags indicating non-physical travel
   * <em>join</em>, <em>talk</em>, <em>button</em>, <em>map</em>, <em>event hub</em>, <em>statue</em> (statues in the museum can be clicked on to teleport)

Absence of a physical travel flag is not definitive evidence that an access point lacks geographic meaning. For example access to [<code>yulgar-s-inn</code>](http://aqwwiki.wikidot.com/yulgar-s-inn) from <code>battleon-town</code> is described with the text "Enter the 'Ye Olde Inn' building on 1st East Street." For this reason, we would like to be reasonably flexible about what we let count as a connection with geographic meaning.

However, presence of non-physical travel flag is also not definitive evidence that an access point lacks geographic meaning. This is because a location can serve as an access point through multiple means. One might walk from point A to point B or teleport from A to B by pressing a button in A. Furthermore, in the text, severla methods may be mentioned on a single-line or on multiple lines in sub-bullets. For example, the Cornelis access point to [<code>mobius</code>](http://aqwwiki.wikidot.com/mobius) is a single bullet that reads "East of Screen 3 or talk to Anise."

In light of this, our current approach is simply to consider a connection physical if the number of physical travel flags is greater or equal to the number of non-physical travel flags. Note however that this does still have limitations. In a scenario where the text is something like "visit the building or talk to Anise", we have no physical travel flags but one non-physical travel flags and thus falsely reject the connection. Nevertheless, based a results we will see later, I think our heuristic is sufficient. In the future, this condition may be adjusted or improved upon. 

## Graph visualization
Once we have built the graphs capturing all connections between locations, we can visualize it to understand the world of AQW. At this point, for simplicity, we do not represent each location with its Wiki extension or its full name, but rather the name code one uses in teleportation by text-command. These name codes are typically short which prevents the graph from being overwhelmed by text. We look at bi-directional graphs (that only include connections if they are reciprocrated) and directional graphs. We also compare what happens when we do not filter connections and when we filter them to indicate physical travel.

### Graph coloring
To aid visualization, we color locations in our graph based on which regions they fall into (the region to color map I use is in [region_color_map.json](https://github.com/r-franks/graph-aqw/blob/main/region_color_map.json)). To determine the region associated with each location, we first go through every region mentioned on the [locations](http://aqwwiki.wikidot.com/locations) main page and note which locations are included in each region. For example, the [Basani Island](http://aqwwiki.wikidot.com/basani-island) region contains the <code>basani</code>, <code>volcano</code> and <code>ruins-of-shurpu</code> locations. The straightforward procedure for doing this is in [aqw_region_pull.py](https://github.com/r-franks/graph-aqw/blob/main/aqw_region_pull.py). When a location is associated with multiple regions, we give precedence to the region which contains the most locations. 

Even now, however, most locations will still not have identified regions. As a result, we cannot yet make a very colorful graph. To remedy this, we apply the following rule: if a location of an unknown region only connects to locations of a specific region (or of an unknown region), we assign it to that specific region. We repeatedly apply this rule until all locations either have assigned regions, connect only to locations of unknown regions, or simultaneously connect to locations in different regions.

### Graph positioning
The AQW world graph turns out to have many disconnected sub-graphs. To visualize everything at once, we therefore apply a custom node positioning approach. Specifically we:
1. Apply the kamada-kawai positioning layout followed by the forceatlas2 layout independently to each connected subcomponent of the full graph
2. Re-scale the positions of each connected sub-component so the smallest distance between two connected nodes is one
3. Determine circles for each connected sub-graph that contains all of its positions, and use a circle-packing algorithm to identify compact placements of these circles
4. Center each connected sub-component of the full AQW graph at the compact placement of its associated circle


