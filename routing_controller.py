from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_0
from ryu.topology.api import get_link, get_switch

from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types



class AddFlowEntry(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(AddFlowEntry, self).__init__(*args, **kwargs)
        # out_port = slice_to_port[dpid][in_port]
        self.slice_to_port = {
            1: {3: 1, 1: 3, 2: 4, 4: 2},
            2: {3: 1, 1: 3, 2: 4, 4: 2},
        }

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # construct flow_mod message and send it.
        mod = parser.OFPFlowMod(
            datapath=datapath,
            match=match,
            cookie=0,
            command=ofproto.OFPFC_ADD,
            idle_timeout=0,
            hard_timeout=0,
            priority=priority,
            flags=ofproto.OFPFF_SEND_FLOW_REM,
            actions=actions,
        )
        datapath.send_msg(mod)

    def _send_package(self, msg, datapath, in_port, actions):
        data = None
        ofproto = datapath.ofproto
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)

    def _get_topology(self, ev):
        # List of Switch objects
        switches = get_switch(self, None)

        # List of Link objects
        links = get_link(self, None)

        print("Switches:")
        for sw in switches:
            print("  dpid =", sw.dp.id)

        print("Links:")
        for link in links:
            # Each link has src and dst, each with dpid and port_no
            print("  %s:%d -> %s:%d" %
                  (link.src.dpid, link.src.port_no,
                   link.dst.dpid, link.dst.port_no))



    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        self._get_topology(ev)
        msg = ev.msg
        datapath = msg.datapath
        in_port = msg.in_port
        dpid = datapath.id

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet
            return

        print(dpid, in_port)
        out_port = self.slice_to_port[dpid][in_port]
        actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
        match = datapath.ofproto_parser.OFPMatch(in_port=in_port)
        self.logger.info("INFO sending packet from s%s (out_port=%s)", dpid, out_port)

        self.add_flow(datapath, 2, match, actions)





