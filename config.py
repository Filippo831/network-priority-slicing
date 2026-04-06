class Config:
    def __init__(self, config_path):

        # router_links_priorities format: { "dpid_str": [ [priority0_ports], [priority1_ports], ... ] }
        # self.router_links_priorities = {
        #     "1": [[1, 3], [2, 4]],
        #     "2": [[1], [2]],
        #     "3": [[1], [2]],
        # }
        self.router_links_priorities = {}

        # mapping of hosts to (switch_dpid, port) will be dynamically populated by the controller based on topology discovery
        self.switch_hosts = {}

        # Host IP list will be dynamically populated by the controller based on topology discovery
        self.hosts_list = []

        # Priority groups for hosts (index corresponds to priority level, lower index = higher priority)
        # self.hosts_priorities_vector = [
        #     ["10.0.0.1", "10.0.0.3", "10.0.0.5"],
        #     ["10.0.0.2", "10.0.0.4", "10.0.0.6"],
        # ]
        self.hosts_priorities_vector = []

    def load_config(self, path):
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                # This automatically sets self.key = value for everything in the JSON
                self.__dict__.update(data)
            print(f"Successfully loaded configuration from {path}")
        else:
            print(f"Warning: {path} not found. Using default empty configurations.")
