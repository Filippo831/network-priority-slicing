import json
import os


class Config:
    def load_config(self, path):
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                # This automatically sets self.key = value for everything in the JSON
                self.__dict__.update(data)
            print(f"Successfully loaded configuration from {path}")
        else:
            print(f"Warning: {path} not found. Using default empty configurations.")

    def __init__(self):
        self.config_path = os.environ.get("CONFIG_PATH", "config.json")
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
        self.hosts_priorities_vector = []
        self.load_config(path=self.config_path)

        print(f"Router Links Priorities: {self.router_links_priorities}")
        print(f"Hosts Priorities Vector: {self.switch_hosts}")
