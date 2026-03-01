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
#   delay: seconds to wait before running the function (default = 10)
# @body
#   cut one of the two links between s1 and s2
def cut_link(net, delay=10):
    time.sleep(delay)
    info("*** Cutting one link between s1 and s2\n")
    s1 = net.get("s1")
    s2 = net.get("s2")
    links = net.linksBetween(s1, s2)
    for l in links:
        if "s1-eth1" in l.intf1.name or "s1-eth1" in l.intf2.name:
            l.intf1.ifconfig("down")
            l.intf2.ifconfig("down")
            info("*** Link between s1 and s2 cut\n")
            break
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
        http_link_config = {"bw": 10, "delay": "1ms", "max_queue_size":1000}

        # high latency, high bandwidth channel
        video_link_config = {"bw": 10, "delay": "5ms", "max_queue_size":1000}
        host_link_config = {"bw": 5, "delay": "1ms", "max_queue_size":1000}

        # Create switch nodes
        for i in range(3):
            sconfig = {"dpid": "%016x" % (i + 1)}
            self.addSwitch("s%d" % (i + 1), **sconfig)

        # Create host nodes
        self.addHost('h1', ip='10.0.0.1', mac='00:00:00:00:00:01')
        self.addHost('h2', ip='10.0.0.2', mac='00:00:00:00:00:02')
        self.addHost('h3', ip='10.0.0.3', mac='00:00:00:00:00:03')
        self.addHost('h4', ip='10.0.0.4', mac='00:00:00:00:00:04')
        self.addHost('h5', ip='10.0.0.5', mac='00:00:00:00:00:05')
        self.addHost('h6', ip='10.0.0.6', mac='00:00:00:00:00:06')


        # Add switch links (one high bandwidth link and one low bandwidth)
        self.addLink("s1", "s2", **http_link_config)
        self.addLink("s1", "s2", **video_link_config)
        self.addLink("s1", "s3", **http_link_config)
        self.addLink("s1", "s3", **video_link_config)

        # Add host links
        self.addLink("h1", "s1", **host_link_config)
        self.addLink("h2", "s1", **host_link_config)
        self.addLink("h3", "s2", **host_link_config)
        self.addLink("h4", "s2", **host_link_config)
        self.addLink("h5", "s3", **host_link_config)
        self.addLink("h6", "s3", **host_link_config)



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

    # # create some traffic between hosts
    h1, h2, h3, h4 = net.get('h1','h2','h3','h4')

    # stream a video from host 3 to host 5
    # h3.cmd("ffmpeg -re -stream_loop -1 -i input_video.mp4 -c copy -f mpegts udp://10.0.0.5:1234 &")

    # automatically cut one of the links between s1 and s2 after 20 seconds
    t = threading.Thread(target=cut_link, args=(net, 20))
    t.start()

    CLI(net)
    net.stop()
