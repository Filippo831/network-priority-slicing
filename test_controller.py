from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.topology.api import get_switch, get_link
from ryu.topology import event

class PriorityBasedController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(PriorityBasedController, self).__init__(*args, **kwargs)

        self.mac_to_port = {}
        self.switches = []
        self.datapaths = {}

        # Priority mappings
        self.hosts_priorities_set = {
            "00:00:00:00:00:01": 0,
            "00:00:00:00:00:02": 1,
            "00:00:00:00:00:03": 0,
            "00:00:00:00:00:04": 1
        }

        self.router_links_priorities = {
            "1": [[1], [2]],  # Switch 1: Port 1 is priority 0, Port 2 is priority 1
            "2": [[1], [2]],  # Switch 2: Same structure
        }

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """Install default table-miss flow entry for switches."""
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Install table-miss flow entry to forward unknown packets to the controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER)]
        self.add_flow(datapath, 0, match, actions)

        self.logger.info(f"Default table-miss flow added to DPID={datapath.id}")

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        """Helper method to install flows."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        instructions = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        if buffer_id:
            mod = parser.OFPFlowMod(
                datapath=datapath, priority=priority,
                buffer_id=buffer_id, match=match, instructions=instructions
            )
        else:
            mod = parser.OFPFlowMod(
                datapath=datapath, priority=priority,
                match=match, instructions=instructions
            )
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """Handle incoming packets."""
        msg = ev.msg
        datapath = msg.datapath
        dpid = datapath.id
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        # Parse the incoming packet
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        dst = eth.dst
        src = eth.src

        # Ignore LLDP packets to avoid looping
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        # Populate learning switch table
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        # Determine priorities of source and destination
        src_priority = self.hosts_priorities_set.get(src, -1)
        dst_priority = self.hosts_priorities_set.get(dst, -1)

        # Use Ryu's priority logic to route packets through priority-based paths
        if dst in self.mac_to_port[dpid]:
            # Destination is known on the current switch
            out_port = self.mac_to_port[dpid][dst]
        else:
            # Destination is not known; flood based on the priority of the source host
            out_port = self._get_priority_flood_port(dpid, src_priority, in_port)

        actions = [parser.OFPActionOutput(out_port)]

        # Install flow entry for destination if the port is known
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            self.add_flow(datapath, 1, match, actions)

        # Send the packet
        data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
        out = parser.OFPPacketOut(
            datapath=datapath, buffer_id=msg.buffer_id,
            in_port=in_port, actions=actions, data=data
        )
        datapath.send_msg(out)

    def _get_priority_flood_port(self, dpid, priority, in_port):
        """Return flood port list based on source priority."""
        dpid_str = str(dpid)
        ports_to_flood = []

        if dpid_str in self.router_links_priorities and priority >= 0:
            flood_ports = self.router_links_priorities[dpid_str][priority]
            ports_to_flood = [port for port in flood_ports if port != in_port]

        return ports_to_flood if ports_to_flood else [ofproto_v1_3.OFPP_FLOOD]

    @set_ev_cls(event.EventSwitchEnter)
    def _switch_enter_handler(self, ev):
        """Handler when a switch connects to the controller."""
        switch = ev.switch
        self.switches.append(switch.dp.id)
        self.datapaths[switch.dp.id] = switch.dp
        self.logger.info(f"Switch connected: DPID={switch.dp.id}")

    @set_ev_cls(event.EventSwitchLeave)
    def _switch_leave_handler(self, ev):
        """Handler when a switch disconnects from the controller."""
        switch = ev.switch
        self.switches.remove(switch.dp.id)
        self.datapaths.pop(switch.dp.id, None)
        self.logger.info(f"Switch disconnected: DPID={switch.dp.id}")
