from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib import hub
from ryu.topology import api as topo_api
import pprint

class SimpleRouting13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleRouting13, self).__init__(*args, **kwargs)

        '''
            self.switch_priority_to_port
            @structure: {dpid: {priority: {dest_sw_dpid: port}}}
            - dpid: current switch id
            - priority: priority of the src host
            - dest_sw_dpid: id of the switch connected to the receiving host
            - port: port to which forward the packet to reach the dest_sw_dpid based on the priority level

            Utilizzato per capire dove inoltrare i pacchetti per ogni switch in base alla prioritá dell'host che ha inviato il pacchetto e allo switch di destinazione
        '''
        self.switch_priority_to_port = {}

        '''
            self.mac_to_port_unknown
            @structure: {dpid: {dst: port}}
            - dpid: current switch id
            - dst: destination mac address
            - port: port to which forward the packet to reach the dest_sw_dpid based on the priority level

            Utilizzato per inoltrare i pacchetti di traffico che non sono generati dagli host
        '''
        self.mac_to_port_unknown = {}

        '''
            self.switch_hosts
            @structure: {mac: (dpid, port)}
            - mac: host mac address
            - dpid: switch id to which the host is connected
            - port: port number on the switch to which the host is connected

            Utilizzato per mappare gli host agli switch a cui sono attaccati e alla porta a cui sono attaccati
        '''
        self.switch_hosts = {}
        
        # self.hosts_list = ["00:00:00:00:00:01", "00:00:00:00:00:03","00:00:00:00:00:02", 
        #                   "00:00:00:00:00:04", "00:00:00:00:00:05", "00:00:00:00:00:06"]

        self.hosts_list = ["00:00:00:00:00:01", "00:00:00:00:00:03","00:00:00:00:00:02"]

        
        '''
            self.hosts_priorities_vector
            @structure: [ [priority_0_host_macs], [priority_1_host_macs], ... ]
            - priority_n_host_macs: list of host mac addresses belonging to priority n

            ogni host viene mappato al suo livello di prioritá in base all'indice dell'array in cui si trova dentro
        '''
        # self.hosts_priorities_vector = [
        #     ["00:00:00:00:00:01", "00:00:00:00:00:03", "00:00:00:00:00:05"], 
        #     ["00:00:00:00:00:02", "00:00:00:00:00:04", "00:00:00:00:00:06"]
        # ]
        self.hosts_priorities_vector = [
            ["00:00:00:00:00:01", "00:00:00:00:00:03"], 
            ["00:00:00:00:00:02"]
        ]
        
        '''
            self.hosts_priorities_set
            @structure: {mac: priority_index}
            - mac: host mac address
            - priority_index: index of the priority level the host belongs to

            Utilizzato per vedere piú velocemente a quale livello di prioritá appartiene un host
        '''
        self.hosts_priorities_set = {}

        # Build the hosts_priorities_set for quick lookup
        for index, priority_array in enumerate(self.hosts_priorities_vector):
            for mac in priority_array:
                self.hosts_priorities_set[mac] = index

        '''
            self.router_links_priorities
            @structure: {dpid: [ [priority_0_ports], [priority_1_ports], ... ] }
            - dpid: switch id
            - priority_n_ports: list of ports on the switch that belong to priority n

            Per ogni switch viene indicata la prioritá della porta in base all'indice dell'array in cui si trova dentro
        '''
        self.router_links_priorities = {
            # "1": [[1, 3], [2, 4]], 
            "1": [[1], [2]], 
            "2": [[1], [2]], 
            # "3": [[1], [2]]
        }

        # Start monitoring thread
        self.monitor_thread = hub.spawn(self._monitor)

        self.datapaths = {}

    '''
        @param
        - ev: EventOFPSwitchFeatures
        @body
        - Install table-miss flow entry to send unmatched packets to the controller

        Ho copiato questa funzione dalla documentazione, non so esattamante cosa faccia
    '''
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    '''
        @param
        - dpid: switch id
        - priority: priority level of the traffic
        - in_port: port on which the packet arrived
        - parser: OpenFlow parser for creating actions
        @return
        - actions: list of OFPActionOutput for all ports belonging to the given priority, excluding in_port
        @body
        - When discovering the route, forward the packet to all the ports of the switch that share the same priority value. Avoid sharing to the input port to prevent loops.
    '''
    def _get_slice_discovery_actions(self, dpid, priority, in_port, parser):
        actions = []

        # get the string value of the number dpid because the set needs a string as key
        dpid_str = str(dpid)

        if dpid_str in self.router_links_priorities:
            # Get the slice ports for the specific priority
            slice_ports = self.router_links_priorities[dpid_str][priority]

            # Create output actions for all slice ports except the in_port
            for port in slice_ports:
                if port != in_port:
                    actions.append(parser.OFPActionOutput(port))
        return actions

    '''
        @param
        - datapath: datapath object representing the switch
        - priority: priority of the flow entry
        - match: match object defining the flow match criteria
        - actions: list of actions to apply for the flow
        - buffer_id: optional buffer ID for the packet
        @body
        - Helper function to add a flow entry to the switch
    '''
    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst, buffer_id=buffer_id) if buffer_id \
            else parser.OFPFlowMod(datapath=datapath, priority=priority,
                                   match=match, instructions=inst)
        datapath.send_msg(mod)

    '''
        @body
        every 10 seconds clear the topology mapping of hosts to switches to account for possible changes in the network
    '''
    def _update_topology(self):
        while True:
            self.switch_hosts = {}
            hub.sleep(10)
            self.hosts_list = topo_api.get_host(self)


    '''
        @param
        - ev: EventOFPPacketIn
        @body
        - Main packet-in handler
        - Updates topology mapping of hosts to switches
        - Handles both unknown/non-priority traffic and sliced/priority traffic
        - Installs flow entries for future packets
    '''
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

        # print the incoming packet info

        # if eth.ethertype == ether_types.ETH_TYPE_LLDP:
        #     # ignore lldp packet
        #     return
        

        # 1. Update Topology: Map hosts to switches
        # We need to know which switch (dpid) and port each host is connected to
        if len(self.switch_hosts) < len(self.hosts_list):
            hosts = topo_api.get_host(self)
            for host in hosts:

                if host.mac in self.hosts_list:
                    self.switch_hosts[host.mac] = (host.port.dpid, host.port.port_no)

        actions = []

        # 2. Handle Non-Priority / Unknown Traffic
        if src not in self.hosts_list or dst not in self.hosts_list:
            # map the src to the dpid so when a packet has to go to that src, it knows to which port to forward the packet
            self.mac_to_port_unknown.setdefault(dpid, {})
            self.mac_to_port_unknown[dpid][src] = in_port
            
            # if the mapping is present, use it to find the right port
            if dst in self.mac_to_port_unknown[dpid]:
                out_port = self.mac_to_port_unknown[dpid][dst]
                actions = [parser.OFPActionOutput(out_port)]
            # if the mapping is not present, flood the packet
            else:
                actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]

            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            
            # If we have a buffer_id, provide it to add_flow to reduce controller load
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
                data=data
            )
            datapath.send_msg(out)

        # 3. Handle Sliced (Priority) Traffic
        else:
            src_priority = self.hosts_priorities_set.get(src)
            # Check if we have not discovered the destination host yet
            if dst not in self.switch_hosts:
                # If destination is unknown, flood ONLY through slice-specific ports
                actions = self._get_slice_discovery_actions(dpid, src_priority, in_port, parser)

            else:
                dst_priority = self.hosts_priorities_set.get(dst)

                dst_sw_dpid, dst_out_port = self.switch_hosts[dst]
                src_sw_dpid, _ = self.switch_hosts[src]

                # Update Routing Table: Learn which port leads to the source switch for this priority, only if not in the same switch
                if src_sw_dpid != dpid:
                    self.switch_priority_to_port.setdefault(dpid, {}).setdefault(src_priority, {})
                    self.switch_priority_to_port[dpid][src_priority][src_sw_dpid] = in_port


                # Case A: Destination host is on the CURRENT switch
                if dst_sw_dpid == dpid:
                    actions = [parser.OFPActionOutput(dst_out_port)]
                
                # Case B: Destination host is on a DIFFERENT switch
                else:
                    # Forwarding Lookup: Do we know which port leads to the dst_sw_dpid?
                    # We check the switch_priority_to_port for an entry for the destination switch
                    known_port = self.switch_priority_to_port.get(dpid, {}).get(src_priority, {}).get(dst_sw_dpid)

                    if known_port:
                        # Route is established! Use the specific port.
                        actions = [parser.OFPActionOutput(known_port)]

                    else:
                        # Route unknown: Forward to all slice ports for discovery
                        actions = self._get_slice_discovery_actions(dpid, src_priority, in_port, parser)

        # 4. Install Flow and Send Packet
        if actions:

            # Install flow to the switch to handle subsequent packets
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)

            # If we have a buffer_id, provide it to add_flow to reduce controller load
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, 100, match, actions, msg.buffer_id)
            else:
                self.add_flow(datapath, 100, match, actions)

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

    '''
    MONITORING
    '''
    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, CONFIG_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
        elif ev.state is None:
            if datapath.id in self.datapaths:
                del self.datapaths[datapath.id]

    def _request_stats(self, datapath):
        self.logger.debug('Sending stats request to: %016x', datapath.id)
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser

        # Request Port Stats
        req = parser.OFPPortStatsRequest(datapath, 0, ofp.OFPP_ANY)
        datapath.send_msg(req)

    '''
        @body
        - Periodically request port statistics from all connected switches
    '''
    def _monitor(self):
        while True:
            for dp in self.datapaths.values():
                self._request_stats(dp)
            hub.sleep(10)

            
    '''
        @body
        - Handle port stats reply messages
        - Calculate and log port that connects the switches to eachother utilization in percentage based on rx and tx bytes
            - priority 0 links: bandwidth = 10 Mbps
            - priority 1 links: bandwidth = 5 Mbps
    '''
    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        body = ev.msg.body

        for stat in body:
            # Check if the port is one of the inter-switch links based on the configured priorities
            dpid_str = str(ev.msg.datapath.id)
            if dpid_str in self.router_links_priorities:
                for priority, ports in enumerate(self.router_links_priorities[dpid_str]):
                    if stat.port_no in ports:
                        # Calculate utilization
                        bandwidth = 10 * 1e6 if priority == 0 else 5 * 1e6  # Convert Mbps to bps
                        rx_bytes = stat.rx_bytes
                        tx_bytes = stat.tx_bytes
                        total_bytes = rx_bytes + tx_bytes
                        utilization = (total_bytes * 8) / bandwidth * 100  # Convert bytes to bits and calculate percentage

                        self.logger.info(
                            "Switch %s Port %s (Priority %s) Utilization: %.2f%%",
                            ev.msg.datapath.id,
                            stat.port_no,
                            priority,
                            utilization
                        )


