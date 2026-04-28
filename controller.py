from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import ipv4, arp, packet, ethernet

from flow_manager import FlowManager
from qos import QoS
from graph import Graph
from config import Config

import networkx as nx
import pprint
import os

try:
    from ryu.topology.event import EventLinkAdd, EventLinkDelete
except Exception:
    EventLinkAdd = None
    EventLinkDelete = None


class SimpleRouting13(app_manager.RyuApp, FlowManager, QoS, Graph, Config):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleRouting13, self).__init__(*args, **kwargs)

        self.is_test = os.environ.get("RYU_TEST", "").lower() == "true"

        self.config_path = os.environ.get("CONFIG_PATH", "config.json")

        self.datapaths = {}

        """
        Topology graph: a NetworkX MultiDiGraph. For each link there is a couple of links monodirectional.:
        STRUCTURE
            - Nodes: switch dpids as strings (e.g., "1", "2", "3")
            - Edges: directed edges representing links between switches, with attributes:
                - port: the port number on the source switch that connects to the destination switch
                - priority: the priority index of the link based on router_links_priorities (or None if not defined)
        """
        self.topo_graph = nx.MultiDiGraph()
        # add all known switches as nodes
        for dpid_str in self.router_links_priorities.keys():
            self.topo_graph.add_node(str(dpid_str))

        """ 
        Learned routing table: {dpid: {priority: {dest_sw_dpid: port}}}

        USAGE
            - dpid: the current switch dpid
            - priority: the priority index of the traffic
            - dst_sw_dpid: the destination switch dpid for which we want to find the output port

            forward_port = self.switch_priority_to_port[dpid][priority][dst_sw_dpid]

        """
        self.switch_priority_to_port = {}
        self.remove_all_flows()

        # Unknown / non-priority traffic learning: {dpid: {dst_ip: port}}
        self.mac_to_port_unknown = {}

        # Inverse mapping: {host_ip: priority_index}
        self.hosts_priorities_set = {}
        for index, priority_array in enumerate(self.hosts_priorities_vector):
            for ip in priority_array:
                self.hosts_priorities_set[ip] = index

        self.is_preempted = False  # flag to indicate if a preemption event has occurred

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)
        ]
        # table-miss
        self.add_flow(datapath, 0, match, actions)
        self.datapaths[datapath.id] = datapath

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match.get("in_port")
        dpid = datapath.id

        # Parse Packet & Validate IPv4
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # Avoid learning from LLDP (neighboring switches)
        if eth.ethertype == 0x88CC:
            return

        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        arp_pkt = pkt.get_protocol(arp.arp)

        if ip_pkt:
            self._update_host_location(ip_pkt.src, dpid, in_port)
        elif arp_pkt:
            self._update_host_location(arp_pkt.src, dpid, in_port)

        if not ip_pkt:
            return

        src_ip, dst_ip = ip_pkt.src, ip_pkt.dst

        # Host Discovery/Filtering
        if src_ip not in self.hosts_list:
            self.hosts_list.append(src_ip)

        if dst_ip not in self.hosts_list:
            return

        """
        Priority Determination:
        - First, we check if the source IP is in our predefined priority sets. If it is, we use that priority index.
        - If it's not in the predefined sets, we assign it the lowest priority
        """
        # pprint.pprint(self.hosts_priorities_set)
        src_priority = self.hosts_priorities_set.get(src_ip)
        if src_priority is None:
            src_priority = len(self.hosts_priorities_vector) - 1
            self.hosts_priorities_set[src_ip] = src_priority

        # Determine Routing Actions
        actions = []


        """
        Routing Logic:
        1. If the destination IP is not known (not in switch_hosts), we treat 
            it as unknown traffic and use discovery actions to find the path using
            the topology graph

        2. If the destination IP is known, we check if it's directly connected 
            to the current switch. If it is, we output to the corresponding port.

        3. If the destination is known but not directly connected, we use the 
            inter-switch routing logic to find the appropriate output port based on 
            the learned routing table or the graph .
        """
        if dst_ip not in self.switch_hosts:
            actions = self._get_discovery_actions(dpid, src_priority, in_port, parser)
        else:
            dst_sw_dpid, dst_out_port = self.switch_hosts[dst_ip]
            src_sw_dpid, _ = self.switch_hosts[src_ip]

            # Learn reverse path so that we can reply back to the source without using the discovery action
            if src_sw_dpid != dpid:
                # copy the state of self.switch_priority_to_port for future comparison
                old_switch_priority_to_port = {
                    dpid: {
                        priority: ports.copy() for priority, ports in priorities.items()
                    } for dpid, priorities in self.switch_priority_to_port.items()
                }

                self.switch_priority_to_port.setdefault(dpid, {}).setdefault(
                    src_priority, {}
                )[src_sw_dpid] = in_port
                
                # print only the differences in the switch_priority_to_port before and after the update
                new_ports = self.switch_priority_to_port[dpid][src_priority]
                old_ports = old_switch_priority_to_port.get(dpid, {}).get(src_priority, {})
                for dst_sw, port in new_ports.items():
                    old_port = old_ports.get(dst_sw)
                    if old_port != port:
                        # print(f"Updated switch_priority_to_port for switch {dpid}, priority {src_priority}, destination switch {dst_sw}: {old_port} -> {port}")
                        pass

                # if test write self.switch_priority_to_port to tests_output/switch_priority_to_port.json
                if self.is_test:
                    import json

                    with open("tests_output/switch_priority_to_port.json", "w") as f:
                        json.dump(self.switch_priority_to_port, f, indent=2)

            if dst_sw_dpid == dpid:
                actions = [parser.OFPActionOutput(dst_out_port)]
            else:
                actions = self._get_inter_switch_actions(
                    msg, dpid, src_priority, dst_sw_dpid, src_ip, dst_ip, in_port
                )

                if known_port:
                    actions = [
                        parser.OFPActionDecNwTtl(),
                        parser.OFPActionOutput(known_port),
                    ]
                    match = parser.OFPMatch(
                        in_port=in_port,
                        ipv4_src=src_ip,
                        ipv4_dst=dst_ip,
                        eth_type=ether_types.ETH_TYPE_IP,
                    )
                    install_flow(match, actions)
                    actions = [parser.OFPActionOutput(known_port)]
                else:
                    # Unknown route: do slice-specific discovery (send to slice ports except in_port)
                    actions = self.routing.get_slice_discovery_actions(
                        dpid,
                        src_priority,
                        in_port,
                        parser,
                        dest_dpid=dst_sw_dpid,
                        nx_graph=self.topo_graph
                    )

                    # if actions is empty, it means this switch has no ports in the source host's priority slice.
                    # If so, check if the src priority is lower than the lowest priority that reaches the destination switch, if so get the
                    # lowest priority available. If not get the next lower priority that reaches the destination switch

                    if not actions:
                        for p_backup in range(len(self.router_links_priorities[str(dpid)])):
                            if p_backup == src_priority:
                                continue
                            actions = self.routing.get_slice_discovery_actions(
                                dpid,
                                p_backup,
                                in_port,
                                parser,
                                dest_dpid=dst_sw_dpid,
                                nx_graph=self.topo_graph
                            )
                            if actions:
                                self.logger.info("No path on priority %s. Backup path found on priority %s", src_priority, p_backup)
                                break
                                
                        available_priorities = sorted(
                            [
                                p
                                for p in self.switch_priority_to_port.get(dpid, {})
                                if dst_sw_dpid in self.switch_priority_to_port[dpid][p]
                            ]
                        )
                        if available_priorities:
                            if src_priority > available_priorities[-1]:
                                selected_priority = available_priorities[-1]
                            else:
                                lower_priorities = [
                                    p for p in available_priorities if p > src_priority
                                ]
                                selected_priority = (
                                    lower_priorities[0] if lower_priorities else None
                                )

                            if selected_priority is not None:
                                known_port = self.switch_priority_to_port[dpid][
                                    selected_priority
                                ][dst_sw_dpid]

                                actions = [parser.OFPActionOutput(known_port)]

        # ---------------------------
        # 3) Install flow + send PacketOut if actions were determined
        # ---------------------------
        if actions:
            # Prepend TTL decrement for all outgoing traffic
            actions = [parser.OFPActionDecNwTtl()] + actions
            self._send_packet_out(datapath, msg, in_port, actions)

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def _port_status_handler(self, ev):
        msg = ev.msg
        reason = msg.reason
        port_no = msg.desc.port_no
        dpid = msg.datapath.id
        ofproto = msg.datapath.ofproto

        if reason not in [ofproto.OFPPR_DELETE, ofproto.OFPPR_MODIFY]:
            return

        # Determine if the port is down based on the reason and port status
        link_down = (msg.desc.state & ofproto.OFPPS_LINK_DOWN) or (
            msg.desc.config & ofproto.OFPPC_PORT_DOWN
        )



        if self.is_test:
            import json

            with open("tests_output/switch_priority_to_port.json", "w") as f:
                json.dump(self.switch_priority_to_port, f, indent=2)

        if not link_down:
            return

        # get all the edges corresponding to the port that went down and remove them from the graph
        edges_to_remove = [
            (u, v, key)
            for u, v, key, attr in self.topo_graph.edges(data=True, keys=True)
            if attr.get("port") == port_no and u == str(dpid)
        ]
        for u, v, key in edges_to_remove:
            self.topo_graph.remove_edge(u, v, key=key)
            # if test write self.topo_graph to tests_output/topo_graph.json
            if self.is_test:
                import json
                from networkx.readwrite import json_graph

                with open("tests_output/topo_graph.json", "w") as f:
                    json.dump(json_graph.node_link_data(self.topo_graph), f, indent=2)

        self._clear_switch_priorities(dpid, port_no)

        # 5. Final flow removal
        self.remove_flows_for_port(dpid, port_no)

    # Topology events: update topology graph when Ryu reports link changes
    if EventLinkAdd is not None:
        """
        Note: This event handler relies on the Ryu topology API to report link additions.
        If you run the Ryu app with the '--observe-links' flag, it will automatically
        populate the topology graph with links as they are discovered.
        The links are mono directional (from src to dst) and the port number is taken from the src of the link.
        So for each connection there should be two edges in the graph, one in each direction,
        with the corresponding port numbers for each switch.
        """

        @set_ev_cls(EventLinkAdd, MAIN_DISPATCHER)
        def _event_link_add(self, ev):
            l = ev.link
            src = l.src
            dst = l.dst
            src_dpid = str(src.dpid)
            dst_dpid = str(dst.dpid)


            # Note: src.port_no is the standard attribute in Ryu Link objects
            src_port = getattr(src, "port_no", None)
            pr = self.find_priority(src_dpid, src_port)

            self.topo_graph.add_edge(
                src_dpid, dst_dpid, key=src_port, port=src_port, priority=pr
            )
            self.switch_priority_to_port = {}
            self.remove_flows_for_port(src.dpid, src_port)

            # if test write self.topo_graph to tests_output/topo_graph.json
            if self.is_test:
                import json
                from networkx.readwrite import json_graph

                with open("tests_output/switch_priority_to_port.json", "w") as f:
                    json.dump(self.switch_priority_to_port, f, indent=2)

                with open("tests_output/topo_graph.json", "w") as f:
                    json.dump(json_graph.node_link_data(self.topo_graph), f, indent=2)
