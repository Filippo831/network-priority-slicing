import unittest
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch, RemoteController
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel
import threading, time
import subprocess
import json
import os


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

def cut_link_test_1(net, delay=10):
    time.sleep(delay)
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

def restore_link_test_1(net, delay=20):
    time.sleep(delay)
    s1 = net.get("s1")
    s2 = net.get("s2")
    links = net.linksBetween(s1, s2)
    for l in links:
        if "s1-eth1" in l.intf1.name or "s1-eth1" in l.intf2.name:
            l.intf1.ifconfig("up")
            l.intf2.ifconfig("up")
            break
    else:
        pass

# class for scenarios testing
class TestScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        my_env = os.environ.copy()
        my_env["RYU_TEST"] = "true"
        # run the ryu controller
        cls.ryu_process = subprocess.Popen(["ryu-manager", "--observe-links", "controller.py", "monitor.py"], env=my_env)

    def test_scenario_1(self):
        '''
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
            - upper link is cut after 10 seconds, then restored after 20 seconds
        '''

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
        net.start()

        # random traffic to learn paths
        for h in net.hosts:
            h.cmd("ping -c 1 10.0.0.%d &" % (int(h.name[1]) % 4 + 1))

        t1 = threading.Thread(target=cut_link_test_1, args=(net, 10))
        t1.start()
        t2 = threading.Thread(target=restore_link_test_1, args=(net, 20))
        t2.start()

        '''
            wait 5 seconds and check if:
            - tests_output/topo_graph.json is equals to tests_output/topo_graph_scenario_1_before_cut.json
            - tests_output/switch_priority_to_port.json is equals to tests_output/switch_priority_to_port_scenario_1_before_cut.json
        '''
        time.sleep(5)
        print("Checking topology and routing before link cut...")
        with open("tests_output/topo_graph.json", "r") as f:
            topo_graph = json.load(f)
        with open("tests_output/topo_graph_scenario_1_before_cut.json", "r") as f:
            expected_topo_graph = json.load(f)
        with open("tests_output/switch_priority_to_port.json", "r") as f:
            switch_priority_to_port = json.load(f)
        with open("tests_output/switch_priority_to_port_scenario_1_before_cut.json", "r") as f:
            expected_switch_priority_to_port = json.load(f)

        self.assertEqual(topo_graph, expected_topo_graph)
        self.assertEqual(switch_priority_to_port, expected_switch_priority_to_port)

        '''
            wait 10 seconds more (15 in total) and check if:
            - tests_output/topo_graph.json is equals to tests_output/topo_graph_scenario_1_after_cut.json
            - tests_output/switch_priority_to_port.json is equals to tests_output/switch_priority_to_port_scenario_1_after_cut.json
        '''
        time.sleep(10)
        print("Checking topology and routing after link cut...")
        with open("tests_output/topo_graph.json", "r") as f:
            topo_graph = json.load(f)
        with open("tests_output/topo_graph_scenario_1_after_cut.json", "r") as f:
            expected_topo_graph = json.load(f)
        with open("tests_output/switch_priority_to_port.json", "r") as f:
            switch_priority_to_port = json.load(f)
        with open("tests_output/switch_priority_to_port_scenario_1_after_cut.json", "r") as f:
            expected_switch_priority_to_port = json.load(f)

        self.assertEqual(topo_graph, expected_topo_graph)
        self.assertEqual(switch_priority_to_port, expected_switch_priority_to_port)

        time.sleep(10)

        net.stop()


    @classmethod
    def tearDownClass(cls):
        if cls.ryu_process:
            cls.ryu_process.terminate()
            cls.ryu_process.wait()


    def test_scenario_2(self):
        # Simulate a scenario where h3 is streaming video to h4
        # and h1 is sending HTTP traffic to h2
        pass

