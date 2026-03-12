import networkx as nx
from ryu.lib.packet import ether_types


class Graph:
    """
    Function to determine the appropriate actions for slice discovery based on the topology graph and priorities.
    - It filters the topology graph to include only edges that match the given priority.
    - It then attempts to find the shortest path from the current switch to the destination switch.
    - If a path is found, it retrieves the output port from the edge attributes and returns the corresponding action.
    - If no path is found, it returns an empty list of actions.
    """

    def get_slice_discovery_actions(
        self, dpid, priority, in_port, parser, dest_dpid, nx_graph=None
    ):
        actions = []
        dpid_str = str(dpid)

        if nx_graph is not None and dest_dpid is not None:

            def edge_filter(u, v, key):
                # Access the edge attributes
                edge_data = nx_graph[u][v][key]
                return edge_data.get("priority") == priority

            subgraph = nx.subgraph_view(nx_graph, filter_edge=edge_filter)

            try:
                path = nx.shortest_path(
                    subgraph, source=dpid_str, target=str(dest_dpid)
                )
                src = path[0]
                dst = path[1]
                edge_data = subgraph.get_edge_data(src, dst)
                matching_ports = [
                    data["port"]
                    for key, data in edge_data.items()
                    if data.get("priority") == priority
                ]

                if len(matching_ports) > 0:
                    actions.append(parser.OFPActionOutput(matching_ports[0]))
            except nx.NetworkXNoPath:
                pass

        return actions

    def display_networkx_graph(self, nx_graph):
        """
        Utility function to print the NetworkX graph in a readable format.
        """
        print("NetworkX Graph:")
        for u, v, attr in nx_graph.edges(data=True):
            print(f"  {u} --({attr})--> {v}")

    """
        Function to determine the appropriate actions for inter-switch communication based on known paths and priorities.
        - If a direct path is known for the given priority, it installs a flow and returns the corresponding action.
        - If no direct path is known, it falls back to discovery actions.
        - If discovery returns no actions, it attempts to find a fallback port based on the priority and the destination switch.
    """

    def _get_inter_switch_actions(
        self, msg, dpid, priority, dst_sw_dpid, src_ip, dst_ip, in_port
    ):
        parser = msg.datapath.ofproto_parser
        known_port = (
            self.switch_priority_to_port.get(dpid, {})
            .get(priority, {})
            .get(dst_sw_dpid)
        )

        if known_port:
            # Install Flow
            match = parser.OFPMatch(
                in_port=in_port,
                ipv4_src=src_ip,
                ipv4_dst=dst_ip,
                eth_type=ether_types.ETH_TYPE_IP,
            )
            flow_actions = [
                parser.OFPActionDecNwTtl(),
                parser.OFPActionOutput(known_port),
            ]
            buffer_id = (
                msg.buffer_id
                if msg.buffer_id != msg.datapath.ofproto.OFP_NO_BUFFER
                else None
            )
            self.add_flow(msg.datapath, 1, match, flow_actions, buffer_id)
            return [parser.OFPActionOutput(known_port)]

        # Fallback to Discovery
        actions = self._get_discovery_actions(
            dpid, priority, in_port, parser, dst_sw_dpid
        )

        # Priority fallback logic if discovery returns nothing
        if not actions:
            fallback_port = self._find_fallback_port(dpid, priority, dst_sw_dpid)
            if fallback_port:
                actions = [parser.OFPActionOutput(fallback_port)]

        return actions

    """
        Function to find the next best port for a given priority if the direct match is not found.
        - It retrieves the available ports for the given switch and priority.
        - It sorts the available ports and selects the next higher port if the source priority is lower than the maximum available port, or the maximum available port if the source priority is higher.
        - It then returns the output port associated with the selected port and destination switch, or None if no suitable port is found.
    """

    def _find_fallback_port(self, dpid, src_priority, dst_sw_dpid):
        switch_ports = self.switch_priority_to_port.get(dpid, {})
        available = sorted(
            [p for p, routes in switch_ports.items() if dst_sw_dpid in routes]
        )

        if not available:
            return None

        # If higher than max, take max. Otherwise find next lower.
        if src_priority > available[-1]:
            selected = available[-1]
        else:
            lower = [p for p in available if p > src_priority]
            selected = lower[0] if lower else None

        return switch_ports[selected][dst_sw_dpid] if selected is not None else None

    def _get_discovery_actions(self, dpid, priority, in_port, parser, dest_dpid=None):
        return self.get_slice_discovery_actions(
            dpid,
            priority,
            in_port,
            parser,
            dest_dpid=dest_dpid,
            nx_graph=self.topo_graph,
        )

    def _send_packet_out(self, datapath, msg, in_port, actions):
        data = None if msg.buffer_id != datapath.ofproto.OFP_NO_BUFFER else msg.data
        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)
