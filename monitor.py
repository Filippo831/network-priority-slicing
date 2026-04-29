from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub
from ryu.lib.packet import packet, ethernet


class NetworkTrafficMonitor(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(NetworkTrafficMonitor, self).__init__(*args, **kwargs)
        self.datapaths = {}
        # Stores previous byte counts: {(dpid, port_no): last_byte_count}
        self.port_stats_cache = {}
        self.monitor_thread = hub.spawn(self._monitor)

    # --- SECTION 2: MONITORING & BANDWIDTH ---
    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                del self.datapaths[datapath.id]

    def _monitor(self):
        while True:
            for dp in self.datapaths.values():
                # Request port stats
                req = dp.ofproto_parser.OFPPortStatsRequest(dp, 0, dp.ofproto.OFPP_ANY)
                dp.send_msg(req)
            hub.sleep(5)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        body = ev.msg.body
        dpid = ev.msg.datapath.id

        # Connect to the routing application to get the preemption state
        routing_app = app_manager.lookup_service_brick("SimpleRouting13")
        if not routing_app:
            print(
                "[Monitor] Warning: Routing application not found. Skipping preemption logic."
            )
            return
        #
        # print(f"\n[Switch {dpid:016x} Traffic Report]")
        # # print(f"{'Port':<5} | {'RX (Mbps)':<12} | {'TX (Mbps)':<12} | {'Total Packets':<12}")
        # # print("-" * 55)
        # print(
        #     f"{'Port':<5} | {'RX (Mbps)':<12} | {'TX (Mbps)':<12} | {'Tot. Packets':<12} | {'Cost':<12} | {'State QoS':<12}"
        # )
        # print("-" * 77)

        tx_speeds = {}

        for stat in sorted(body, key=lambda x: x.port_no):
            if stat.port_no == 0xFFFFFFFE:
                continue  # Skip local port

            key = (dpid, stat.port_no)
            prev_rx, prev_tx = self.port_stats_cache.get(key, (0, 0))

            # Calculate throughput: (Current - Previous) * 8 bits / 5 seconds / 10^6
            rx_speed = (stat.rx_bytes - prev_rx) * 8 / 5 / 10**6
            tx_speed = (stat.tx_bytes - prev_tx) * 8 / 5 / 10**6

            self.port_stats_cache[key] = (stat.rx_bytes, stat.tx_bytes)
            tx_speeds[stat.port_no] = tx_speed

            # Cost calculation based on utilization
            B_max = 10.0
            U = min(
                tx_speed, B_max - 0.1
            )  # Avoid division by zero and unrealistic speeds
            cost = 1.0 + 5.0 * (1 / (1 - (U / B_max)))

            state = "PREEMPTED" if routing_app.is_preempted else "NORMAL"

            # print(f"{stat.port_no:<5} | {rx_speed:<12.4f} | {tx_speed:<12.4f} | {stat.rx_packets + stat.tx_packets:<12}")
            # print(
            #     f"{stat.port_no:<5} | {rx_speed:<12.4f} | {tx_speed:<12.4f} | {stat.rx_packets + stat.tx_packets:<12} | {cost:<12.2f} | {state:<12}"
            # )

        # Preemption logic
        if str(dpid) in routing_app.preemption_map:
            config = routing_app.preemption_map[str(dpid)]
            v_port = config['video']
            h_port = config['http']
            
            v_speed = tx_speeds.get(v_port, 0)
            is_active = routing_app.is_preempted.get(dpid, False)

            # If the video port is congested (over 8.5 Mbps) and we haven't preempted yet -> Preempt the video traffic
            if not is_active and v_speed > 8.5:
                routing_app.execute_preemption(dpid, v_port, h_port)

            # If the video port is not congested (under 6 Mbps) and we have preempted -> Rollback the video traffic
            elif is_active and v_speed < 6.0:
                routing_app.execute_rollback(dpid, v_port, h_port)
