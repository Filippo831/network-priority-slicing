class Config:
    def __init__(self):

        # router_links_priorities format: { "dpid_str": [ [priority0_ports], [priority1_ports], ... ] }
        self.router_links_priorities = {
            "1": [[1, 3], [2, 4]],
            "2": [[1], [2]],
            "3": [[1], [2]],
        }

        # Static mapping of hosts to (switch_dpid, port)
        # self.switch_hosts = {
        #     "10.0.0.1": (1, 5),
        #     "10.0.0.2": (1, 6),
        #     "10.0.0.3": (2, 3),
        #     "10.0.0.4": (2, 4),
        #     "10.0.0.5": (3, 3),
        #     "10.0.0.6": (3, 4),
        # }

        # mapping of hosts to (switch_dpid, port) will be dynamically populated by the controller based on topology discovery
        self.switch_hosts = {}

        # Host IP list
        # self.hosts_list = [
        #     "10.0.0.1",
        #     "10.0.0.2",
        #     "10.0.0.3",
        #     "10.0.0.4",
        #     "10.0.0.5",
        #     "10.0.0.6",
        # ]

        # Host IP list will be dynamically populated by the controller based on topology discovery
        self.hosts_list = []

        # Priority groups for hosts (index corresponds to priority level, lower index = higher priority)
        self.hosts_priorities_vector = [
            ["10.0.0.1", "10.0.0.3", "10.0.0.5"],
            ["10.0.0.2", "10.0.0.4", "10.0.0.6"],
        ]
