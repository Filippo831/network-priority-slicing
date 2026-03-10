class FlowManager():
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


    def find_priority(self, dpid, port_no):
        """Return the priority index for a given switch dpid and port number, or None."""
        priorities = self.router_links_priorities.get(str(dpid), [])
        for idx, ports in enumerate(priorities):
            if port_no in ports:
                return idx
        return None
    
    def _clear_switch_priorities(self, dpid, port_no):
        """Helper to handle the nested dictionary cleanup."""
        if dpid not in self.switch_priority_to_port:
            return

        for priority, dst_sw_dict in self.switch_priority_to_port[dpid].items():
            keys_to_remove = [
                dst_sw for dst_sw, port in dst_sw_dict.items() 
                if port == port_no
            ]
            for dst_sw in keys_to_remove:
                del dst_sw_dict[dst_sw]
