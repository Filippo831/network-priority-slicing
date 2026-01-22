from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.topology import api as topo_api
import pprint

class SimpleRouting13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleRouting13, self).__init__(*args, **kwargs)

        # Structure: {dpid: {priority: {dest_sw_dpid: port}}}
        self.switch_priority_to_port = {}
        self.mac_to_port_unknown = {}
        self.switch_hosts = {}
        
        self.hosts_list = ["00:00:00:00:00:01", "00:00:00:00:00:03","00:00:00:00:00:02", 
                          "00:00:00:00:00:04", "00:00:00:00:00:05", "00:00:00:00:00:06"]
        
        self.hosts_priorities_vector = [
            ["00:00:00:00:00:01", "00:00:00:00:00:03", "00:00:00:00:00:05"], 
            ["00:00:00:00:00:02", "00:00:00:00:00:04", "00:00:00:00:00:06"]
        ]
        
        self.hosts_priorities_set = {}
        for index, priority_array in enumerate(self.hosts_priorities_vector):
            for mac in priority_array:
                self.hosts_priorities_set[mac] = index

        # Port mapping for slicing
        self.router_links_priorities = {
            "1": [[1, 3], [2, 4]], 
            "2": [[1], [2]], 
            "3": [[1], [2]]
        }

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def _get_slice_discovery_actions(self, dpid, priority, in_port, parser):
        """Returns a list of output actions for all ports belonging to a priority slice."""
        actions = []
        dpid_str = str(dpid)
        if dpid_str in self.router_links_priorities:
            # Get the slice ports for the specific priority
            slice_ports = self.router_links_priorities[dpid_str][priority]
            for port in slice_ports:
                if port != in_port:
                    actions.append(parser.OFPActionOutput(port))
        return actions

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst, buffer_id=buffer_id) if buffer_id \
            else parser.OFPFlowMod(datapath=datapath, priority=priority,
                                   match=match, instructions=inst)
        datapath.send_msg(mod)


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        dst = eth.dst
        src = eth.src
        dpid = datapath.id

        # 1. Update Topology: Map hosts to switches
        # We need to know which switch (dpid) and port each host is connected to
        hosts = topo_api.get_host(self)
        for host in hosts:
            # Structure: { mac: (dpid, port) }
            self.switch_hosts[host.mac] = (host.port.dpid, host.port.port_no)


        actions = []

        # 2. Handle Non-Priority / Unknown Traffic
        if src not in self.hosts_list or dst not in self.hosts_list:
            self.mac_to_port_unknown.setdefault(dpid, {})
            self.mac_to_port_unknown[dpid][src] = in_port
            
            if dst in self.mac_to_port_unknown[dpid]:
                out_port = self.mac_to_port_unknown[dpid][dst]
                actions = [parser.OFPActionOutput(out_port)]
            else:
                actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]

        # 3. Handle Sliced (Priority) Traffic
        else:
            src_priority = self.hosts_priorities_set.get(src)
            dst_priority = self.hosts_priorities_set.get(dst)
            
            # Check if we have discovered the destination host yet
            if dst not in self.switch_hosts:
                # If destination is unknown, flood ONLY through slice-specific ports
                actions = self._get_slice_discovery_actions(dpid, dst_priority, in_port, parser)
            else:
                dst_sw_dpid, dst_out_port = self.switch_hosts[dst]
                src_sw_dpid, _ = self.switch_hosts[src]
                if src_sw_dpid != dpid:
                    self.switch_priority_to_port.setdefault(dpid, {}).setdefault(src_priority, {})
                    self.switch_priority_to_port[dpid][src_priority][src_sw_dpid] = in_port

                # Case A: Destination host is on the CURRENT switch
                if dst_sw_dpid == dpid:
                    actions = [parser.OFPActionOutput(dst_out_port)]
                
                # Case B: Destination host is on a DIFFERENT switch
                else:
                    pprint.pp(self.switch_priority_to_port)

                    # Forwarding Lookup: Do we know which port leads to the dst_sw_dpid?
                    # We check the switch_priority_to_port for an entry for the destination switch
                    known_port = self.switch_priority_to_port.get(dpid, {}).get(dst_priority, {}).get(dst_sw_dpid)

                    if known_port:
                        # Route is established! Use the specific port.
                        actions = [parser.OFPActionOutput(known_port)]
                    else:
                        # Route unknown: Forward to all slice ports for discovery
                        actions = self._get_slice_discovery_actions(dpid, dst_priority, in_port, parser)

        # 4. Install Flow and Send Packet
        if actions:
            # Install flow to the switch to handle subsequent packets
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            
            # If we have a buffer_id, provide it to add_flow to reduce controller load
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, 1, match, actions, msg.buffer_id)
                return
            else:
                self.add_flow(datapath, 1, match, actions)

            # Send the current packet out
            data = None
            if msg.buffer_id == ofproto.OFP_NO_BUFFER:
                data = msg.data

            out = parser.OFPPacketOut(
                datapath=datapath,
                buffer_id=msg.buffer_id,
                in_port=in_port,
                actions=actions,
                data=data
            )
            datapath.send_msg(out)

