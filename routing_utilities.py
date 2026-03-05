import networkx as nx


class Routing:
    def __init__(self, router_links_priorities):
        """
        router_links_priorities: { "dpid_str": [ [priority0_ports], [priority1_ports], ... ] }
        """
        self.router_links_priorities = router_links_priorities or {}

    '''
        @param
    '''

    def get_slice_discovery_actions(
        self, dpid, priority, in_port, parser, dest_dpid, nx_graph=None
    ):
        actions = []
        dpid_str = str(dpid)

        # create a networkx graph with only the edges with the same priority as the input priority
        if nx_graph is not None and dest_dpid is not None:
            '''
                The networkx graph edges is expected to have the following format:
                    self.topo_graph.add_edge(src, dst, key=src_port, port=src_port, priority=pr)
                Filter the edges based on the priority and create a new graph with only the edges with the same priority as the input priority. Then, find the shortest path from the current dpid to the destination dpid and add the actions to the actions list based on the ports in the path.
            '''
            def edge_filter(u, v, key):
                # Access the edge attributes
                edge_data = nx_graph[u][v][key]
                return edge_data.get('priority') == priority
            
            subgraph = nx.subgraph_view(
                nx_graph,
                filter_edge=edge_filter
            )

            try:
                path = nx.shortest_path(subgraph, source=dpid_str, target=str(dest_dpid))
                src = path[0]
                dst = path[1]
                edge_data = subgraph.get_edge_data(src, dst)
                matching_ports = [
                    data['port'] 
                    for key, data in edge_data.items() 
                    if data.get('priority') == priority
                ]

                if len(matching_ports) > 0:
                    actions.append(parser.OFPActionOutput(matching_ports[0]))
            except nx.NetworkXNoPath:
                pass
                # print(f"No path found from {dpid_str} to {dest_dpid} with priority {priority}")

        return actions

    

    def display_networkx_graph(self, nx_graph):
        """
        Utility function to print the NetworkX graph in a readable format.
        """
        print("NetworkX Graph:")
        for u, v, attr in nx_graph.edges(data=True):
            print(f"  {u} --({attr})--> {v}")
