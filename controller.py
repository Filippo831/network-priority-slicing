from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import ipv4
import pprint
import sys
import networkx as nx
import copy

try:
    from ryu.topology.event import EventLinkAdd, EventLinkDelete
except Exception:
    EventLinkAdd = None
    EventLinkDelete = None

from routing_utilities import Routing


class SimpleRouting13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleRouting13, self).__init__(*args, **kwargs)

        # router_links_priorities format: { "dpid_str": [ [priority0_ports], [priority1_ports], ... ] }
        self.router_links_priorities = {
            "1": [[1, 3], [2, 4]],
            "2": [[1], [2]],
            "3": [[1], [2]],
        }

        self.datapaths = {}

        self.routing = Routing(self.router_links_priorities)

        '''
        Topology graph: a NetworkX MultiDiGraph. For each link there is a couple of links monodirectional.:
        STRUCTURE
            - Nodes: switch dpids as strings (e.g., "1", "2", "3")
            - Edges: directed edges representing links between switches, with attributes:
                - port: the port number on the source switch that connects to the destination switch
                - priority: the priority index of the link based on router_links_priorities (or None if not defined)
        '''
        self.topo_graph = nx.MultiDiGraph()
        # add all known switches as nodes
        for dpid_str in self.router_links_priorities.keys():
            self.topo_graph.add_node(str(dpid_str))

        # Learned routing table: {dpid: {priority: {dest_sw_dpid: port}}}
        self.switch_priority_to_port = {}

        # Unknown / non-priority traffic learning: {dpid: {dst_ip: port}}
        self.mac_to_port_unknown = {}

        # Static mapping of hosts to (switch_dpid, port)
        self.switch_hosts = {
            "10.0.0.1": (1, 5),
            "10.0.0.2": (1, 6),
            "10.0.0.3": (2, 3),
            "10.0.0.4": (2, 4),
            "10.0.0.5": (3, 3),
            "10.0.0.6": (3, 4),
        }

        # Host IP list
        self.hosts_list = [
            "10.0.0.1",
            "10.0.0.2",
            "10.0.0.3",
            "10.0.0.4",
            "10.0.0.5",
            "10.0.0.6",
        ]

        # Priority groups (index = priority level)
        self.hosts_priorities_vector = [
            ["10.0.0.1", "10.0.0.3", "10.0.0.5"],
            ["10.0.0.2", "10.0.0.4", "10.0.0.6"],
        ]

        # Inverse mapping: {host_ip: priority_index}
        self.hosts_priorities_set = {}
        for index, priority_array in enumerate(self.hosts_priorities_vector):
            for ip in priority_array:
                self.hosts_priorities_set[ip] = index

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

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        if buffer_id:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                priority=priority,
                match=match,
                instructions=inst,
                buffer_id=buffer_id,
            )
        else:
            mod = parser.OFPFlowMod(
                datapath=datapath, priority=priority, match=match, instructions=inst
            )
        datapath.send_msg(mod)

    def find_priority(self, dpid, port_no):
        """Return the priority index for a given switch dpid and port number, or None."""
        priorities = self.router_links_priorities.get(str(dpid), [])
        for idx, ports in enumerate(priorities):
            if port_no in ports:
                return idx
        return None

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        in_port = msg.match.get("in_port")
        dpid = datapath.id

        # Inline helpers scoped to this method (small lambdas kept local)
        install_flow = lambda match, actions, buf_id=msg.buffer_id: self.add_flow(
            datapath,
            1,
            match,
            actions,
            buf_id if buf_id != ofproto.OFP_NO_BUFFER else None,
        )
        send_packetout = (
            lambda actions, data=None, buf_id=msg.buffer_id: datapath.send_msg(
                parser.OFPPacketOut(
                    datapath=datapath,
                    buffer_id=buf_id,
                    in_port=in_port,
                    actions=actions,
                    data=data,
                )
            )
        )

        # Parse packet
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[
            0
        ]  # we keep eth in case extension needed later
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if not ip_pkt:
            # we only handle IPv4 packets in this controller
            return
        src_ip = ip_pkt.src
        dst_ip = ip_pkt.dst

        # WARNING: Dynamic learning of hosts disabled for static topology
        # learn where the hosts are placed
        # if src_ip not in self.switch_hosts:
        #     self.logger.info("Learning host %s on Switch %s, Port %s", src_ip, dpid, in_port)
        #     self.switch_hosts[src_ip] = (dpid, in_port)
        #
        #     # Optional: Also add to hosts_list if you use it for filtering
        #     if src_ip not in self.hosts_list:
        #         self.hosts_list.append(src_ip)

        # add unknown hosts to hosts_list
        if src_ip not in self.hosts_list:
            self.hosts_list.append(src_ip)

        if dst_ip not in self.hosts_list:
            # unknown destination host: ignore packet
            return

        # ---------------------------
        # 2) Sliced / Priority traffic
        # ---------------------------
        # Retrieve priority of source; default to None (should exist for known hosts)

        src_priority = self.hosts_priorities_set.get(src_ip)

        # if source host not found in priorities set, add it with lowest priority
        if src_priority is None:
            self.hosts_priorities_set[src_ip] = len(self.hosts_priorities_vector) - 1
            src_priority = self.hosts_priorities_set[src_ip]

        # If destination host is unknown to static topology: slice-specific discovery
        if dst_ip not in self.switch_hosts:
            # Unknown route: do slice-specific discovery (send to slice ports except in_port)
            actions = self.routing.get_slice_discovery_actions(
                dpid,
                src_priority,
                in_port,
                parser,
                dest_dpid=dst_sw_dpid,
                nx_graph=self.topo_graph
            )

        else:
            # Both hosts are known in topology: get their switch/port attachments
            dst_sw_dpid, dst_out_port = self.switch_hosts[dst_ip]
            src_sw_dpid, _ = self.switch_hosts[src_ip]

            # Learn which port leads to the source switch for this priority (if not on same switch)
            if src_sw_dpid != dpid:
                self.switch_priority_to_port.setdefault(dpid, {}).setdefault(
                    src_priority, {}
                )
                self.switch_priority_to_port[dpid][src_priority][src_sw_dpid] = in_port

            # If destination is on the same switch: deliver locally
            if dst_sw_dpid == dpid:
                actions = [parser.OFPActionOutput(dst_out_port)]
            else:
                # Check if we have a learned port to reach dst switch for this priority
                known_port = (
                    self.switch_priority_to_port.get(dpid, {})
                    .get(src_priority, {})
                    .get(dst_sw_dpid)
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
            # decrement ttl of a packet to avoid loops in case of discovery
            actions = [parser.OFPActionDecNwTtl()] + actions
            data = None if msg.buffer_id != ofproto.OFP_NO_BUFFER else msg.data
            send_packetout(actions, data)

    def remove_flows_for_port(self, dpid, port_no):
        # remove all flows for the deleted ports to force rediscovery
        parser = self.datapaths[dpid].ofproto_parser
        ofproto = self.datapaths[dpid].ofproto
        mod = parser.OFPFlowMod(
            datapath=self.datapaths[dpid],
            command=ofproto.OFPFC_DELETE,
            out_port=port_no,
            out_group=ofproto.OFPG_ANY,
            table_id=ofproto.OFPTT_ALL,
            match=parser.OFPMatch(),
        )
        self.datapaths[dpid].send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def _port_status_handler(self, ev):
        msg = ev.msg
        reason = msg.reason
        port_no = msg.desc.port_no
        dpid = msg.datapath.id
        ofproto = msg.datapath.ofproto

        if reason == ofproto.OFPPR_DELETE or reason == ofproto.OFPPR_MODIFY:
            # if port is down remove learned routes
            link_down = (msg.desc.state & ofproto.OFPPS_LINK_DOWN) or (
                msg.desc.config & ofproto.OFPPC_PORT_DOWN
            )

            if link_down:
                # remove the edges connected to this port from the topology graph
                edges_to_remove = []
                for u, v, key, attr in self.topo_graph.edges(data=True, keys=True):
                    if attr.get("port") == port_no and u == str(dpid):
                        edges_to_remove.append((u, v, key))
                for u, v, key in edges_to_remove:
                    self.topo_graph.remove_edge(u, v, key=key)
                        

                # self.logger.info(
                #     "Port %s on Switch %s is down. Removing learned routes for this port",
                #     port_no,
                #     dpid,
                # )
                if dpid in self.switch_priority_to_port:
                    # find all priorities and destination switches that used this port and remove them
                    for priority in self.switch_priority_to_port[dpid]:
                        priorities_dict = self.switch_priority_to_port[dpid][priority]
                        keys_to_remove = [
                            dst_sw
                            for dst_sw, port in priorities_dict.items()
                            if port == port_no
                        ]

                        for dst_sw in keys_to_remove:
                            del self.switch_priority_to_port[dpid][priority][dst_sw]
                self.remove_flows_for_port(dpid, port_no)

    # Topology events: update topology graph when Ryu reports link changes
    if EventLinkAdd is not None:
        '''
        Note: This event handler relies on the Ryu topology API to report link additions. 
        If you run the Ryu app with the '--observe-links' flag, it will automatically 
        populate the topology graph with links as they are discovered.
        The links are mono directional (from src to dst) and the port number is taken from the src of the link.
        So for each connection there should be two edges in the graph, one in each direction, 
        with the corresponding port numbers for each switch.
        '''
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

            self.topo_graph.add_edge(src_dpid, dst_dpid, key=src_port, port=src_port, priority=pr)

