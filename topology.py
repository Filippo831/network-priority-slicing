#!/usr/bin/python3

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch, RemoteController
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel
import threading, time


# @param
#   net: network object
#   delay: seconds to wait before running the function (default = 30)
#
# @body
#   add a host 'h5' to the network linked to s2 through http_link_config
def add_late_hosts(net, delay=30):
    http_link_config = {"bw": 1}
    hconfig = {"inNamespace": True}
    time.sleep(delay)
    h5 = net.addHost("h5", **hconfig)
    net.addLink("h5", "s2", **http_link_config)
    net.configHosts()
    info("added new host h5 connected to router s2\n")


class FVTopo(Topo):
    def __init__(self):
        # Initialize topology
        Topo.__init__(self)

        # CONFIGURATION EXAMPLE
        # self.addLink( host, switch, bw=10, delay='5ms', loss=2,
        # max_queue_size=1000, use_htb=True )

        # Create template host, switch, and link
        hconfig = {"inNamespace": True}

        # low latency, low bandwidth channel
        http_link_config = {"bw": 1, "delay": "5ms"}

        # high latency, high bandwidth channel
        video_link_config = {"bw": 10, "delay": "50ms"}
        host_link_config = {}

        # Create switch nodes
        for i in range(2):
            sconfig = {"dpid": "%016x" % (i + 1)}
            self.addSwitch("s%d" % (i + 1), **sconfig)

        # Create host nodes
        for i in range(4):
            self.addHost("h%d" % (i + 1), **hconfig)

        # Add switch links (one high bandwidth link and one low bandwidth)
        self.addLink("s1", "s2", **http_link_config)
        self.addLink("s1", "s2", **video_link_config)

        # Add host links
        self.addLink("h1", "s1", **host_link_config)
        self.addLink("h2", "s1", **host_link_config)
        self.addLink("h3", "s2", **host_link_config)
        self.addLink("h4", "s2", **host_link_config)


topos = {"fvtopo": (lambda: FVTopo())}

if __name__ == "__main__":
    setLogLevel("info")
    topo = FVTopo()
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

    # start the thread that will add a new host after "delay" seconds of runtime
    t = threading.Thread(target=add_late_hosts, args=(net, 10))
    t.deamon = True
    t.start()

    CLI(net)
    net.stop()
