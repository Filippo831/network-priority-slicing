from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.topology import api as topo_api


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
        self.hosts_list = ["00:00:00:00:00:01", "00:00:00:00:00:03","00:00:00:00:00:02", "00:00:00:00:00:04"]
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

    def get_host_ports(self, datapath):
        # 1. Get all active ports on this switch
        all_ports = [port.port_no for port in datapath.ports.values() if port.state == 0]
        
        # 2. Get all ports that are used to connect to other switches (links)
        switch_links = topo_api.get_all_link(self)
        link_ports = []
        for link in switch_links:
            if link.src.dpid == datapath.id:
                link_ports.append(link.src.port_no)
                
        # 3. Host ports = All ports - Link ports
        host_ports = [p for p in all_ports if p not in link_ports]
        return host_ports

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
        # self.logger.info("{} : {}, router = {}\n".format(src, dst, dpid))
        # self.logger.info("{}\n".format(datapath.to_str()))

        host_ports = self.get_host_ports(datapath)
        print(host_ports)

        # TODO: handle incoming packets
        # - check the input mac address and get the priority number
        # - if not defined the port yet, flood it to the port with same priority number (maybe create a selector to define if using only the port with the same priority number or ever the lower priorities)

        # actions = []
        # if src in self.hosts_priorities_set.keys() and dst not in self.hosts_list:
        #     input_packet_priority = self.hosts_priorities_set[src]
        #
        #     out_port = self.router_links_priorities[str(dpid)][input_packet_priority]
        #     for port in out_port:
        #         if port != in_port:
        #             actions.append(parser.OFPActionOutput(port))
        #
        # else:
        #     out_port = ofproto.OFPP_FLOOD
        #     actions = [parser.OFPActionOutput(out_port)]
        out_port = ofproto.OFPP_FLOOD
        actions = [parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_in next time
        match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
        if msg.buffer_id != ofproto.OFP_NO_BUFFER:
            self.add_flow(datapath, 1, match, actions, msg.buffer_id)
            return
        else:
            self.add_flow(datapath, 1, match, actions)

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)

