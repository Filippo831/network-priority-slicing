import json
import os
import subprocess
import time
import unittest

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch, RemoteController
from mininet.topo import Topo


class TopologyTest1(Topo):
    def __init__(self):
        Topo.__init__(self)

        hconfig = {"inNamespace": True}

        # low latency, low bandwidth channel
        http_link_config = {
            "bw": 10,
            "delay": "5ms",
            "max_queue_size": 1000,
            "use_htb": True,
        }

        # high latency, high bandwidth channel
        video_link_config = {
            "bw": 10,
            "delay": "1ms",
            "max_queue_size": 1000,
            "use_htb": True,
        }
        host_link_config = {
            "bw": 20,
            "delay": "1ms",
            "max_queue_size": 1000,
            "use_htb": True,
        }  # Host links are faster to avoid bottlenecks at the edge of the network

        # Create switch nodes
        for i in range(2):
            sconfig = {"dpid": "%016x" % (i + 1)}
            self.addSwitch("s%d" % (i + 1), **sconfig)

        # Create host nodes
        self.addHost("h1", ip="10.0.0.1", mac="00:00:00:00:00:01")
        self.addHost("h2", ip="10.0.0.2", mac="00:00:00:00:00:02")
        self.addHost("h3", ip="10.0.0.3", mac="00:00:00:00:00:03")
        self.addHost("h4", ip="10.0.0.4", mac="00:00:00:00:00:04")

        # Add switch links (one high bandwidth link and one low bandwidth)
        self.addLink("s1", "s2", **video_link_config)  # Port 1: Priority 0 (Video)
        self.addLink("s1", "s2", **http_link_config)  # Port 2: Priority 1 (HTTP)

        # Add host links
        self.addLink("h1", "s1", **host_link_config)
        self.addLink("h2", "s1", **host_link_config)
        self.addLink("h3", "s2", **host_link_config)
        self.addLink("h4", "s2", **host_link_config)


def cut_link_test_1(net):
    # time.sleep(delay)
    s1 = net.get("s1")
    s2 = net.get("s2")
    links = net.linksBetween(s1, s2)
    for l in links:
        if "s1-eth1" in l.intf1.name or "s1-eth1" in l.intf2.name:
            l.intf1.ifconfig("down")
            l.intf2.ifconfig("down")
            break
    else:
        pass
    print("\nLink between s1-eth1 and s2-eth1 cut")



class TopologyTest2(Topo):
    def __init__(self):
        Topo.__init__(self)

        hconfig = {"inNamespace": True}

        # low latency, low bandwidth channel
        http_link_config = {
            "bw": 10,
            "delay": "5ms",
            "max_queue_size": 1000,
            "use_htb": True,
        }

        # high latency, high bandwidth channel
        video_link_config = {
            "bw": 10,
            "delay": "1ms",
            "max_queue_size": 1000,
            "use_htb": True,
        }
        host_link_config = {
            "bw": 20,
            "delay": "1ms",
            "max_queue_size": 1000,
            "use_htb": True,
        }  # Host links are faster to avoid bottlenecks at the edge of the network

        # Create switch nodes
        for i in range(3):
            sconfig = {"dpid": "%016x" % (i + 1)}
            self.addSwitch("s%d" % (i + 1), **sconfig)

        # Create host nodes
        self.addHost("h1", ip="10.0.0.1", mac="00:00:00:00:00:01")
        self.addHost("h2", ip="10.0.0.2", mac="00:00:00:00:00:02")
        self.addHost("h3", ip="10.0.0.3", mac="00:00:00:00:00:03")
        self.addHost("h4", ip="10.0.0.4", mac="00:00:00:00:00:04")
        self.addHost("h5", ip="10.0.0.5", mac="00:00:00:00:00:05")
        self.addHost("h6", ip="10.0.0.6", mac="00:00:00:00:00:06")

        # Add switch links (one high bandwidth link and one low bandwidth)
        self.addLink("s1", "s2", **video_link_config)
        self.addLink("s1", "s2", **http_link_config)
        self.addLink("s1", "s3", **http_link_config)
        self.addLink("s1", "s3", **http_link_config)

        # Add host links
        self.addLink("h1", "s1", **host_link_config)
        self.addLink("h2", "s1", **host_link_config)
        self.addLink("h3", "s2", **host_link_config)
        self.addLink("h4", "s2", **host_link_config)
        self.addLink("h5", "s3", **host_link_config)
        self.addLink("h6", "s3", **host_link_config)

def cut_link_test_2(net):
    # time.sleep(delay)
    s1 = net.get("s1")
    s3 = net.get("s3")
    links = net.linksBetween(s1, s3)
    for l in links:
        if "s1-eth3" in l.intf1.name or "s1-eth3" in l.intf2.name:
            l.intf1.ifconfig("down")
            l.intf2.ifconfig("down")
            break
    else:
        pass
    print("\nLink between s1-eth3 and s3-eth1 cut")

class TopologyTest3(Topo):
    def __init__(self):
        Topo.__init__(self)

        hconfig = {"inNamespace": True}

        # low latency, low bandwidth channel
        http_link_config = {
            "bw": 10,
            "delay": "5ms",
            "max_queue_size": 1000,
            "use_htb": True,
        }
        host_link_config = {
            "bw": 20,
            "delay": "1ms",
            "max_queue_size": 1000,
            "use_htb": True,
        }  # Host links are faster to avoid bottlenecks at the edge of the network

        # Create switch nodes
        for i in range(3):
            sconfig = {"dpid": "%016x" % (i + 1)}
            self.addSwitch("s%d" % (i + 1), **sconfig)

        # Create host nodes
        self.addHost("h1", ip="10.0.0.1", mac="00:00:00:00:00:01")
        self.addHost("h2", ip="10.0.0.2", mac="00:00:00:00:00:02")
        self.addHost("h3", ip="10.0.0.3", mac="00:00:00:00:00:03")

        self.addLink("s1", "s2", **http_link_config)
        self.addLink("s2", "s3", **http_link_config)
        self.addLink("s1", "s3", **http_link_config)

        self.addLink("h1", "s1", **host_link_config)
        self.addLink("h2", "s2", **host_link_config)
        self.addLink("h3", "s3", **host_link_config)

def cut_link_test_3(net):
    # time.sleep(delay)
    s1 = net.get("s1")
    s2 = net.get("s2")
    links = net.linksBetween(s1, s2)
    for l in links:
        if "s1-eth1" in l.intf1.name or "s1-eth1" in l.intf2.name:
            l.intf1.ifconfig("down")
            l.intf2.ifconfig("down")
            break
    else:
        pass
    print("\nLink between s1-eth1 and s2-eth1 cut")

def normalize_topo_graph(graph):
    normalized_links = []
    for link in graph["links"]:
        src = link["source"]
        dst = link["target"]
        port = link["port"]
        priority = link["priority"]
        # create a normalized representation of the link that is independent of the order of nodes and links
        normalized_link = {
            "nodes": sorted([src, dst]),
            "port": port,
            "priority": priority,
        }
        normalized_links.append(normalized_link)
    # sort the list of links to make it independent of the order of links
    normalized_links.sort(key=lambda x: (x["nodes"], x["port"], x["priority"]))
    return normalized_links



# class for scenarios testing
class TestScenarios(unittest.TestCase):
    def setUp(self):
        self.ryu_process = None

    def start_ryu_controller(self, config_file):
        if self.ryu_process:
            self.ryu_process.terminate()
            self.ryu_process.wait()

        my_env = os.environ.copy()
        my_env["RYU_TEST"] = "true"
        my_env["CONFIG_PATH"] = config_file
        self.ryu_process = subprocess.Popen(
            ["ryu-manager", "--observe-links", "controller.py", "monitor.py"],
            env=my_env,
        )
        print("\nWaiting for Ryu controller to start...")
        time.sleep(5)  # wait for the controller to start and load the config
        print("Ryu controller started with config:", config_file)

    def tearDown(self):
        if self.ryu_process:
            self.ryu_process.terminate()
            self.ryu_process.wait()
            input("\nPress Enter to move to the next scenario...")

    def test_scenario_1(self):
        """
        FIRST SCENARIO
        @topology:
        h1 --- s1 --- s2 --- h3
               |  ---  |
               h2      h4

        @priorities:
        - h1, h3: priority 0
        - h2, h4: priority 1
        - s1-s2 upper link: priority 0 (video)
        - s1-s2 lower link: priority 1 (HTTP)

        @scenario:
        - upper link is cut after 10 seconds
        """
        self.start_ryu_controller(config_file="./configurations/test_1.json")

        print("\nFIRST SCENARIO: Link cut between s1 and s2 with priority 0")

        topo = TopologyTest1()
        net = Mininet(
            topo=topo,
            controller=RemoteController("c0", ip="127.0.0.1"),
            switch=OVSKernelSwitch,
            build=False,
            autoSetMacs=True,
            autoStaticArp=True,
            link=TCLink,
        )
        net.build()

        # empty tests_output/topo_graph.json and tests_output/switch_priority_to_port.json
        with open("tests_output/topo_graph.json", "w") as f:
            pass
        with open("tests_output/switch_priority_to_port.json", "w") as f:
            pass

        try:
            net.start()

            time.sleep(4)

            # random traffic to learn paths
            for i in range(5):
                for h in net.hosts:
                    for j in range(1, 5):
                    # h.cmd("ping -c 1 10.0.0.%d &" % (int(h.name[1]) % 6 + 1))
                        if h.name != "h%d" % j:
                            h.cmd("ping -c 1 10.0.0.%d &" % j)

            """
                check if:
                - tests_output/topo_graph.json is equals to tests_output/topo_graph_scenario_1_before_cut.json
                - tests_output/switch_priority_to_port.json is equals to tests_output/switch_priority_to_port_scenario_1_before_cut.json
            """
            time.sleep(4)
            print("\nChecking topology and routing before link cut...")
            with open("tests_output/topo_graph.json", "r") as f:
                topo_graph = json.load(f)
            with open("tests_output/test_1/topo_graph_scenario_1_before_cut.json", "r") as f:
                expected_topo_graph = json.load(f)
            with open("tests_output/switch_priority_to_port.json", "r") as f:
                switch_priority_to_port = json.load(f)
            with open(
                "tests_output/test_1/switch_priority_to_port_scenario_1_before_cut.json", "r"
            ) as f:
                expected_switch_priority_to_port = json.load(f)

            # test this equalities and if false print the differences in a human readable way
            self.assertEqual(
                normalize_topo_graph(topo_graph),
                normalize_topo_graph(expected_topo_graph),
            )

            self.assertEqual(switch_priority_to_port, expected_switch_priority_to_port)

            pingall_result = net.pingAll()
            self.assertEqual(pingall_result, 0)


            print("Checked topology and routing before link cut")

            cut_link_test_1(net)
            time.sleep(4)
            for i in range(5):
                for h in net.hosts:
                    for j in range(1, 5):
                    # h.cmd("ping -c 1 10.0.0.%d &" % (int(h.name[1]) % 6 + 1))
                        if h.name != "h%d" % j:
                            h.cmd("ping -c 1 10.0.0.%d &" % j)
            time.sleep(4)

            """
                after the link cut check if:
                - tests_output/topo_graph.json is equals to tests_output/topo_graph_scenario_1_after_cut.json
                - tests_output/switch_priority_to_port.json is equals to tests_output/switch_priority_to_port_scenario_1_after_cut.json
            """

            print("\nChecking topology and routing after link cut...")
            pingall_result = net.pingAll()
            self.assertEqual(pingall_result, 0)

            with open("tests_output/topo_graph.json", "r") as f:
                topo_graph = json.load(f)
            with open("tests_output/test_1/topo_graph_scenario_1_after_cut.json", "r") as f:
                expected_topo_graph = json.load(f)
            with open("tests_output/switch_priority_to_port.json", "r") as f:
                switch_priority_to_port = json.load(f)
            with open(
                "tests_output/test_1/switch_priority_to_port_scenario_1_after_cut.json", "r"
            ) as f:
                expected_switch_priority_to_port = json.load(f)

            self.assertEqual(
                normalize_topo_graph(topo_graph),
                normalize_topo_graph(expected_topo_graph),
            )
            self.assertEqual(switch_priority_to_port, expected_switch_priority_to_port)

            print("Checked topology and routing after link cut")

        finally:
            net.stop()
            print("\nFIRST SCENARIO test completed\n")

    def test_scenario_2(self):
        '''
        SECOND SCENARIO
        @topology:
        h5 --- s3 --- s1 --- s2 --- h3
              /   --- /\ ---  \
             /       /  \      \
            h6      h1  h2     h4

        @priorities:
        - h1, h3, h5: priority 0
        - h2, h4, h6: priority 1
        - s1-s2 upper link: priority 0 (video)
        - s1-s2 lower link: priority 1 (HTTP)
        - s1-s3 upper link: priority 0 (video)
        - s1-s3 lower link: priority 1 (HTTP)

        @scenario:
        - T = 10s: h1->h3 traffic goes up to 15Mbps
        - T = 15s: upper link between s1 and s3 is cut
        - T = 35s: h1->h3 traffic close connection
        '''
        self.start_ryu_controller(config_file="./configurations/test_2.json")

        print("\nSECOND SCENARIO: Preemption of video traffic from h1 to h3 and link cut between s1 and s3")

        topo = TopologyTest2()
        net = Mininet(
            topo=topo,
            controller=RemoteController("c0", ip="127.0.0.1"),
            switch=OVSKernelSwitch,
            build=False,
            autoSetMacs=True,
            autoStaticArp=True,
            link=TCLink,
        )
        net.build()
        
        with open("tests_output/topo_graph.json", "w") as f:
            pass
        with open("tests_output/switch_priority_to_port.json", "w") as f:
            pass

        try:
            net.start()
            time.sleep(4)

            # random traffic to learn paths sending a ping from each host to each other host
            for i in range(5):
                for h in net.hosts:
                    for j in range(1, 7):
                    # h.cmd("ping -c 1 10.0.0.%d &" % (int(h.name[1]) % 6 + 1))
                        if h.name != "h%d" % j:
                            h.cmd("ping -c 1 10.0.0.%d &" % j)
            time.sleep(10)

            # check topology and routing at init state
            print("\nChecking topology and routing at the beginning...")
            with open("tests_output/topo_graph.json", "r") as f:
                topo_graph = json.load(f)
            with open("tests_output/test_2/init_topo_graph.json", "r") as f:
                expected_topo_graph = json.load(f)
            with open("tests_output/switch_priority_to_port.json", "r") as f:
                switch_priority_to_port = json.load(f)
            with open(
                "tests_output/test_2/init_switch_priority_to_port.json", "r"
            ) as f:
                expected_switch_priority_to_port = json.load(f)

            self.assertEqual(
                normalize_topo_graph(topo_graph),
                normalize_topo_graph(expected_topo_graph),
            )
            self.assertEqual(switch_priority_to_port, expected_switch_priority_to_port)
            print("Checked topology and routing at the beginning")

            # increase traffic from h1 to h3 to 15Mbps
            print("\nIncreasing traffic from h1 to h3 to 15Mbps...")
            h1 = net.get("h1")
            h3 = net.get("h3")
            h1.cmd("iperf -c %s -u -b 15M -t 10 &" % h3.IP())
            time.sleep(10)

            # check if the port s1-eth1 had increased the bandwidth to 15Mbps and s1-eth2 had decreased to 5Mbps
            print("\nChecking bandwidth settings after traffic increase...")
            s1 = net.get("s1")
            s1_eth1_bw = s1.cmd("tc qdisc show dev s1-eth1")
            s1_eth2_bw = s1.cmd("tc qdisc show dev s1-eth2")
            self.assertIn("rate 15Mbit", s1_eth1_bw)
            self.assertIn("rate 5Mbit", s1_eth2_bw)
            print("Checked bandwidth settings after traffic increase")

            time.sleep(3)
            cut_link_test_2(net)
            
            # random traffic to learn paths sending a ping from each host to each other host
            for i in range(5):
                for h in net.hosts:
                    for j in range(1, 7):
                        if h.name != "h%d" % j:
                            h.cmd("ping -c 1 10.0.0.%d &" % j)

            time.sleep(3)

            # check the topology and routing after the link cut
            print("\nChecking topology and routing after link cut...")
            with open("tests_output/topo_graph.json", "r") as f:
                topo_graph = json.load(f)
            with open("tests_output/test_2/after_cut_topo_graph.json", "r") as f:
                expected_topo_graph = json.load(f)
            with open("tests_output/switch_priority_to_port.json", "r") as f:
                switch_priority_to_port = json.load(f)
            with open(
                "tests_output/test_2/after_cut_switch_priority_to_port.json", "r"
            ) as f:
                expected_switch_priority_to_port = json.load(f)

            self.assertEqual(
                normalize_topo_graph(topo_graph),
                normalize_topo_graph(expected_topo_graph),
            )
            self.assertEqual(switch_priority_to_port, expected_switch_priority_to_port)
            print("Checked topology and routing after link cut")

            # run pingall and check if all hosts can reach each other
            print("\nChecking connectivity between all hosts after link cut...")
            pingall_result = net.pingAll()
            self.assertEqual(pingall_result, 0)
            print("Checked connectivity between all hosts after link cut")

            time.sleep(5)
            # check if the bandwidth went back to normal after traffic decrease (10Mbps for both ports)
            print("\nChecking bandwidth settings after traffic decrease...")
            s1_eth1_bw = s1.cmd("tc qdisc show dev s1-eth1")
            s1_eth2_bw = s1.cmd("tc qdisc show dev s1-eth2")
            self.assertIn("rate 10Mbit", s1_eth1_bw)
            self.assertIn("rate 10Mbit", s1_eth2_bw)
            print("Checked bandwidth settings after traffic decrease")
        
        finally:
            net.stop()
            print("\nSECOND SCENARIO test completed\n")

    def test_scenario_3(self):
        '''
            THIRD SCENARIO
            @topology:
                   h1       
                   |        
                   s1       
                  /  \     
            h2--s2 -- s3--h3

            @priorities:
            - h1, h2, h3: priority 0
            - s1-s2 link: priority 0
            - s2-s3 link: priority 0
            - s1-s3 link: priority 0

            @scenario:
            - T = 10s: link between s1 and s2 is cut
        '''
        self.start_ryu_controller(config_file="./configurations/test_3.json")

        print("\nTHIRD SCENARIO: Link cut between s1 and s2 considering a close topology with multiple paths between hosts")

        topo = TopologyTest3()
        net = Mininet(
            topo=topo,
            controller=RemoteController("c0", ip="127.0.0.1"),
            switch=OVSKernelSwitch,
            build=False,
            autoSetMacs=True,
            autoStaticArp=True,
            link=TCLink,
        )

        net.build()

        with open("tests_output/topo_graph.json", "w") as f:
            pass
        with open("tests_output/switch_priority_to_port.json", "w") as f:
            pass

        try:
            net.start()

            time.sleep(4)

            # random traffic to learn paths sending a ping from each host to each other host
            for i in range(3):
                for h in net.hosts:
                    for j in range(1, 4):
                        if h.name != "h%d" % j:
                            h.cmd("ping -c 1 10.0.0.%d &" % j)

            time.sleep(4)

            # check topology and routing at init state
            print("\nChecking topology and routing at the beginning...")
            with open("tests_output/topo_graph.json", "r") as f:
                topo_graph = json.load(f)
            with open("tests_output/test_3/init_topo_graph.json", "r") as f:
                expected_topo_graph = json.load(f)
            with open("tests_output/switch_priority_to_port.json", "r") as f:
                switch_priority_to_port = json.load(f)
            with open(
                "tests_output/test_3/init_switch_priority_to_port.json", "r"
            ) as f:
                expected_switch_priority_to_port = json.load(f)

            self.assertEqual(
                normalize_topo_graph(topo_graph),
                normalize_topo_graph(expected_topo_graph),
            )
            self.assertEqual(switch_priority_to_port, expected_switch_priority_to_port)
            print("Checked topology and routing at the beginning")
            
            # test connectivity between hosts before link cut
            print("\nChecking connectivity between all hosts before link cut...")
            pingall_result = net.pingAll()
            self.assertEqual(pingall_result, 0)
            print("Checked connectivity between all hosts before link cut")
            
            time.sleep(3)
            cut_link_test_3(net)
            time.sleep(3)

            # random traffic to learn paths sending a ping from each host to each other host
            for i in range(3):
                for h in net.hosts:
                    for j in range(1, 4):
                        if h.name != "h%d" % j:
                            h.cmd("ping -c 1 10.0.0.%d &" % j)

            time.sleep(4)
            print("\nChecking connectivity between all hosts after link cut...")
            pingall_result = net.pingAll()
            self.assertEqual(pingall_result, 0)
            print("Checked connectivity between all hosts after link cut")
            # check the topology and routing after the link cut
            print("\nChecking topology and routing after link cut...")
            with open("tests_output/topo_graph.json", "r") as f:
                topo_graph = json.load(f)
            with open("tests_output/test_3/after_cut_topo_graph.json", "r") as f:
                expected_topo_graph = json.load(f)
            with open("tests_output/switch_priority_to_port.json", "r") as f:
                switch_priority_to_port = json.load(f)
            with open(
                "tests_output/test_3/after_cut_switch_priority_to_port.json", "r"
            ) as f:
                expected_switch_priority_to_port = json.load(f)

            self.assertEqual(
                normalize_topo_graph(topo_graph),
                normalize_topo_graph(expected_topo_graph),
            )
            self.assertEqual(switch_priority_to_port, expected_switch_priority_to_port)
            print("Checked topology and routing after link cut")

            # test connectivity between hosts after link cut

        finally:
            net.stop()
            print("\nTHIRD SCENARIO test completed\n")
