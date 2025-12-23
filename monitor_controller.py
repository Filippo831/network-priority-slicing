from operator import attrgetter

from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
from ryu.app import simple_switch_13

from ryu.lib.packet import packet
from ryu.lib.packet import ethernet


class SimpleMonitor13(simple_switch_13.SimpleSwitch13):
    def __init__(self, *args, **kwargs):
        super(SimpleMonitor13, self).__init__(*args, **kwargs)
        self.connections = {}
        self.hosts = []
        self.monitor_thread = hub.spawn(self._monitor)
        self.datapaths = {}

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.logger.debug("register datapath: %016x", datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug("unregister datapath: %016x", datapath.id)
                del self.datapaths[datapath.id]

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        if ev.msg.msg_len < ev.msg.total_len:
            self.logger.debug(
                "packet truncated: only %s of %s bytes",
                ev.msg.msg_len,
                ev.msg.total_len,
            )
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        dst = eth.dst
        src = eth.src

        dpid = datapath.id
        self.connections.setdefault(dpid, {})
        self.connections[dpid][src] = in_port

        if src not in self.hosts:
            self.hosts.append(src)
            self.logger.info(
                "Host %s connected to switch %s on port %s", src, dpid, in_port
            )

        # Do not process the packet further
        return

    def _monitor(self):
        while True:
            for dp in self.datapaths.values():
                self._request_stats(dp)
            hub.sleep(10)

    def _request_stats(self, datapath):
        self.logger.debug("send stats request: %016x", datapath.id)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        body = ev.msg.body

        self.logger.info(
            "datapath         port     "
            "rx-pkts  rx-bytes rx-error "
            "tx-pkts  tx-bytes tx-error"
        )
        self.logger.info(
            "---------------- -------- "
            "-------- -------- -------- "
            "-------- -------- --------"
        )
        for stat in sorted(body, key=attrgetter("port_no")):
            self.logger.info(
                "%016x %8x %8d %8d %8d %8d %8d %8d",
                ev.msg.datapath.id,
                stat.port_no,
                stat.rx_packets,
                stat.rx_bytes,
                stat.rx_errors,
                stat.tx_packets,
                stat.tx_bytes,
                stat.tx_errors,
            )
