class QoS():
    def resize_port_bandwidth(self, dpid, port_no, new_bw_mbps):
        """Uses 'tc' command of Linux to change the size of the HW queue of the switch."""
        interface_name = f"s{dpid}-eth{port_no}"
        cmd = [
            "sudo", "tc", "qdisc", "replace", "dev", interface_name,
            "root", "tbf", "rate", f"{new_bw_mbps}mbit",
            "burst", "100kb", "latency", "50ms"
        ]
        try:
            subprocess.run(cmd, check=True, stderr=subprocess.DEVNULL)
            self.logger.info(f"*** QOS HW UPDATE: {interface_name} configured with {new_bw_mbps} Mbps!")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error in tc command for {interface_name}")

    def execute_preemption(self, dpid, video_port, http_port):
        """Preempt the video traffic by giving it more bandwidth and limiting HTTP when congestion is detected."""
        if self.is_preempted: return
        self.is_preempted = True
        self.logger.info("\n*** [PREEMPTION] 15 Mbps requested on video port! Preempting HTTP traffic to prioritize video.")
        # Resize the ports: give more bandwidth to video and limit HTTP, keeping the total bandwidth within the max capacity of the link (20 Mbps in this case)
        self.resize_port_bandwidth(dpid, video_port, 15)
        self.resize_port_bandwidth(dpid, http_port, 5)

    def execute_rollback(self, dpid, video_port, http_port):
        """Rollback the preemption by restoring the original bandwidth settings when congestion is resolved."""
        if not self.is_preempted: return
        self.is_preempted = False
        self.logger.info("\n*** [ROLLBACK] Congestion resolved on video port. Rolling back to original bandwidth settings.")
        self.resize_port_bandwidth(dpid, video_port, 10)
        self.resize_port_bandwidth(dpid, http_port, 10)

