from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet


'''
    ryu application that creates 2 slices in the topology
    - high latency, high bandwidth slice
    - low latency, low bandwidth slice

    it automatically deviate the flow of the low latency packets to the high latency connection if its fails

'''
class SimpleRouting13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleRouting13, self).__init__(*args, **kwargs)

        # TODO:remove this if the rest works
        # define the ports for each switch that will use the low latency path
        # self.low_latency_hosts = {
        #     1: [3],
        #     2: [3],
        # }
        
        # define the priority of the hosts in an array where the index indicates the priority, lower is better
        self.hosts_priorities_vector = [["00:00:00:00:00:01", "00:00:00:00:00:03"], ["00:00:00:00:00:02", "00:00:00:00:00:04"]]
        self.hosts_priorities_set = {}

        # generate a set of "mac" = "priority" entries to lookup faster when checking the slice
        for index, priority_array in enumerate(self.hosts_priorities_vector):
            for mac in priority_array:
                self.hosts_priorities_set[mac] = index

        # TODO:remove this if the rest works
        # define for each router which port is associated with the low latency connection
        # self.low_latency_link = {
        #     1: 1,
        #     2: 1,
        # }

        # define the priority of links between the routers. The lowest priority of the router gets the traffic from that priority level to the lowest.
        # {"router_id": [vector of priorities]}
        self.router_links_priorities = {"1": [[1], [2]], "2": [[1], [2]]}

        # create a set that links for each router, its port to the priority level
        self.router_links_priorities_set = {}
        for router, value in self.router_links_priorities.items():
            self.router_links_priorities_set[router] = {}
            for index, priority_array in enumerate(value):
                for port_number in priority_array:
                    self.router_links_priorities_set[router][port_number] = index


        # init the connection between the two router, then they are automatically updated when something happens 
        # TODO: see if it's possible to generate this automatically
        # self.router_to_router_ports = {
        #     b"s1": [1,2],
        #     b"s2": [1,2],
        # }

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # install table-miss flow entry
        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)
        ]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                buffer_id=buffer_id,
                priority=priority,
                match=match,
                instructions=inst,
            )
        else:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                priority=priority,
                match=match,
                instructions=inst,
            )
        datapath.send_msg(mod)

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
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        dst = eth.dst
        src = eth.src

        dpid = datapath.id

        # # when the port number is greater than or equal to 3, it means the packet is coming from a host
        # # connected to the switch. In this case, we decide the output port based on whether the host is in the low latency list or not.
        # if in_port >= 3:
        #     if in_port in self.low_latency_hosts[dpid] and 1 in self.router_to_router_ports[("s{}".format(dpid)).encode("utf-8")]:
        #         self.logger.info("low latency for host %s on switch %s", src, dpid)
        #         out_port = 1
        #     elif 2 in self.router_to_router_ports[("s{}".format(dpid)).encode("utf-8")]:
        #         self.logger.info("high bandwidth for host %s on switch %s", src, dpid)
        #         out_port = 2
        #
        # else:
        #     # default behavior: flood
        #     out_port = ofproto.OFPP_FLOOD

        # TODO: handle incoming packets
        # - check the input mac address and get the priority number
        # - if not defined the port yet, flood it to the port with same priority number (maybe create a selector to define if using only the port with the same priority number or ever the lower priorities)

        if src in self.hosts_priorities_set.keys()
            input_packet_priority = self.hosts_priorities_set[src]

            output_ports = router_links_priorities[str(dpid)][input_packet_priority]
            self.logger.info(output_ports)

        # actions = [parser.OFPActionOutput(out_port)]
        #
        # # install a flow to avoid packet_in next time
        # match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
        # if msg.buffer_id != ofproto.OFP_NO_BUFFER:
        #     self.add_flow(datapath, 1, match, actions, msg.buffer_id)
        #     return
        # else:
        #     self.add_flow(datapath, 1, match, actions)
        #
        # data = None
        # if msg.buffer_id == ofproto.OFP_NO_BUFFER:
        #     data = msg.data
        #
        # out = parser.OFPPacketOut(
        #     datapath=datapath,
        #     buffer_id=msg.buffer_id,
        #     in_port=in_port,
        #     actions=actions,
        #     data=data,
        # )
        # datapath.send_msg(out)

    # get port events to check when a connection is not available anymore, if so change the route
    # @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    # def _port_status_handler(self, ev):
    #     msg = ev.msg
    #     reason = msg.reason
    #     port_no = msg.desc.port_no
    #
    #     router = msg.desc.name.split(b"-")[0]
    #
    #     ofproto = msg.datapath.ofproto
    #     if reason == ofproto.OFPPR_ADD:
    #         self.logger.info("port added %s", port_no)
    #     elif reason == ofproto.OFPPR_DELETE:
    #         self.logger.info("port deleted %s", port_no)
    #         print(router)
    #         self.router_to_router_ports[router].remove(port_no)
    #     elif reason == ofproto.OFPPR_MODIFY:
    #         self.logger.info("port modified %s", port_no)
    #     else:
    #         self.logger.info("Illeagal port state %s %s", port_no, reason)
    #
