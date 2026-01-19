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
#   destination: host object to which traffic will be sent
#   delay: seconds to wait before running the function (default = 30)
#
# @body
#   add a host 'h5' to the network linked to s2 through http_link_config
# def add_late_hosts(net, destination, delay=30):
#     time.sleep(delay)
#     info("*** Adding late host h5\n")
#     hconfig = {"inNamespace": True}
#     http_link_config = {"bw": 1, "delay": "5ms"}
#
#     h5 = net.addHost("h5", **hconfig)
#     s2 = net.get("s2")
#     net.addLink(h5, s2, **http_link_config)
#     info("*** Late host h5 added and linked to s2\n")
#     h5_intf = h5.defaultIntf()
#     h5.setIP("10.0.0.5/24", intf=h5_intf)
#     h5.cmd("ip link set {} up".format(h5_intf))
#
#     # generate traffic between h5 and destination for 60 seconds every 5
#     # destination.cmd("iperf -s &")
#     # h5.cmd("iperf -c {} -t 60 -i 5 &".format(destination.IP()))

# @param
#   net: network object
#   delay: seconds to wait before running the function (default = 10)
# @body
#   cut one of the two links between s1 and s2
def cut_link(net, delay=10):
    time.sleep(delay)
    info("*** Cutting one link between s1 and s2\n")
    s1 = net.get("s1")
    s2 = net.get("s2")
    links = net.linksBetween(s1, s2)
    if len(links) >= 2:
        link_to_cut = links[0]
        net.delLink(link_to_cut)
        info("*** Link between s1 and s2 cut\n")
    else:
        info("*** Not enough links to cut between s1 and s2\n")

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

    # create some traffic between hosts
    h1, h2, h3, h4 = net.get('h1','h2','h3','h4')

    # generate traffic between h1 and h3 for 60 seconds every 5
    # h3.cmd("iperf -s &")
    # h1.cmd("iperf -c {} -t 60 -i 5 &".format(h3.IP()))

    # generate traffic between h2 and h4 for 60 seconds every 5
    # h4.cmd("iperf -s &")
    # h2.cmd("iperf -c {} -t 60 -i 5 &".format(h4.IP()))

    # start the thread that will cut the link between s1 and s2 after "delay" seconds of runtime
    # t2 = threading.Thread(target=cut_link, args=(net, 10))
    # t2.daemon = True
    # t2.start()

    # start the thread that will add a new host after "delay" seconds of runtime
    # t = threading.Thread(target=add_late_hosts, args=(net, h1, 10))
    # t.daemon = True
    # t.start()

    CLI(net)
    net.stop()
