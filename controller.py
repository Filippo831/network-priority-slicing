from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import ipv4

from routing_utilities import Routing


class SimpleRouting13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleRouting13, self).__init__(*args, **kwargs)

        # router_links_priorities format: { "dpid_str": [ [priority0_ports], [priority1_ports], ... ] }
        self.router_links_priorities = {
            "1": [[1, 3], [2, 4]],
            "2": [[1], [2]],
            "3": [[1], [2]]
        }
        self.routing = Routing(self.router_links_priorities)

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
        self.hosts_list = ["10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4", "10.0.0.5", "10.0.0.6"]

        # Priority groups (index = priority level)
        self.hosts_priorities_vector = [
            ["10.0.0.1", "10.0.0.3", "10.0.0.5"],
            ["10.0.0.2", "10.0.0.4", "10.0.0.6"]
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
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        # table-miss
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst, buffer_id=buffer_id)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                   match=match, instructions=inst)
        datapath.send_msg(mod)



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
            datapath, 1, match, actions, buf_id if buf_id != ofproto.OFP_NO_BUFFER else None
        )
        send_packetout = lambda actions, data=None, buf_id=msg.buffer_id: datapath.send_msg(
            parser.OFPPacketOut(datapath=datapath,
                                buffer_id=buf_id,
                                in_port=in_port,
                                actions=actions,
                                data=data)
        )

        # Parse packet
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]  # we keep eth in case extension needed later
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if not ip_pkt:
            # we only handle IPv4 packets in this controller
            return
        src_ip = ip_pkt.src
        dst_ip = ip_pkt.dst

        # ---------------------------
        # 1) Non-priority / Unknown traffic (learning switch behavior)
        # ---------------------------
        if src_ip not in self.hosts_list or dst_ip not in self.hosts_list:
            # Learn source ip -> in_port for this switch
            self.mac_to_port_unknown.setdefault(dpid, {})
            self.mac_to_port_unknown[dpid][src_ip] = in_port

            # If destination known on this switch, forward to that port; else flood
            out_port = self.mac_to_port_unknown[dpid].get(dst_ip)
            if out_port is not None:
                actions = [parser.OFPActionOutput(out_port)]
            else:
                actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]

            # Install a low-priority flow that matches ip src/dst and in_port
            match = parser.OFPMatch(in_port=in_port,
                                    ipv4_src=src_ip,
                                    ipv4_dst=dst_ip,
                                    eth_type=ether_types.ETH_TYPE_IP)
            install_flow(match, actions)

            # If packet was not buffered on switch, include the payload in PacketOut
            data = None if msg.buffer_id != ofproto.OFP_NO_BUFFER else msg.data
            send_packetout(actions, data)
            return  # finished handling non-priority traffic

        # ---------------------------
        # 2) Sliced / Priority traffic
        # ---------------------------
        # Retrieve priority of source; default to None (should exist for known hosts)
        src_priority = self.hosts_priorities_set.get(src_ip)
        if src_priority is None:
            # No known priority mapping for source: fall back to flooding
            actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
            match = parser.OFPMatch(in_port=in_port,
                                    ipv4_src=src_ip,
                                    ipv4_dst=dst_ip,
                                    eth_type=ether_types.ETH_TYPE_IP)
            install_flow(match, actions)
            data = None if msg.buffer_id != ofproto.OFP_NO_BUFFER else msg.data
            send_packetout(actions, data)
            return

        # If destination host is unknown to static topology: slice-specific discovery
        if dst_ip not in self.switch_hosts:
            actions = self.routing.get_slice_discovery_actions(dpid, src_priority, in_port, parser)

        else:
            # Both hosts are known in topology: get their switch/port attachments
            dst_sw_dpid, dst_out_port = self.switch_hosts[dst_ip]
            src_sw_dpid, _ = self.switch_hosts[src_ip]

            # Learn which port leads to the source switch for this priority (if not on same switch)
            if src_sw_dpid != dpid:
                self.switch_priority_to_port.setdefault(dpid, {}).setdefault(src_priority, {})
                self.switch_priority_to_port[dpid][src_priority][src_sw_dpid] = in_port

            # If destination is on the same switch: deliver locally
            if dst_sw_dpid == dpid:
                actions = [parser.OFPActionOutput(dst_out_port)]
            else:
                # Check if we have a learned port to reach dst switch for this priority
                known_port = (self.switch_priority_to_port.get(dpid, {})
                              .get(src_priority, {})
                              .get(dst_sw_dpid))
                if known_port:
                    actions = [parser.OFPActionOutput(known_port)]
                else:
                    # Unknown route: do slice-specific discovery (send to slice ports except in_port)
                    actions = self.routing.get_slice_discovery_actions(dpid, src_priority, in_port, parser)

        # ---------------------------
        # 3) Install flow + send PacketOut if actions were determined
        # ---------------------------
        if actions:
            match = parser.OFPMatch(in_port=in_port,
                                    ipv4_src=src_ip,
                                    ipv4_dst=dst_ip,
                                    eth_type=ether_types.ETH_TYPE_IP)
            install_flow(match, actions)
            data = None if msg.buffer_id != ofproto.OFP_NO_BUFFER else msg.data
            send_packetout(actions, data)


