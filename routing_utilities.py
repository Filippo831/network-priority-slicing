class Routing:
    def __init__(self, router_links_priorities):
        """
        router_links_priorities: { "dpid_str": [ [priority0_ports], [priority1_ports], ... ] }
        """
        self.router_links_priorities = router_links_priorities or {}

    def get_slice_discovery_actions(self, dpid, priority, in_port, parser):
        """
        Return a list of parser.OFPActionOutput(...) for all ports in the slice
        corresponding to 'priority' on switch 'dpid', excluding in_port.
        - dpid: numeric datapath id (converted to str for lookup)
        - priority: integer index of priority slice
        - in_port: port from which the packet arrived (excluded from outputs)
        - parser: datapath.ofproto_parser to construct actions
        """
        actions = []
        dpid_str = str(dpid)
        if dpid_str in self.router_links_priorities:
            # Safety: ensure priority index exists
            priorities_list = self.router_links_priorities[dpid_str]
            if 0 <= priority < len(priorities_list):
                slice_ports = priorities_list[priority]
                for port in slice_ports:
                    if port != in_port:
                        actions.append(parser.OFPActionOutput(port))
        return actions
