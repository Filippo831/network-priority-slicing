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

def demo_orchestrator(net):
    info("\n*** [DEMO] PHASE 1: Video and HTTP at 10 Mbps\n")
    h1, h2, h3, h4 = net.get('h1', 'h2', 'h3', 'h4')

    # 1. HTTP traffic (Priority 1, h2 -> h4 on Switch 2): Uses 8 Mbps 
    h4.popen('iperf -s -u -i 1')
    h2.popen('iperf -c 10.0.0.4 -u -b 8M -t 60')
    
    # 2. Video traffic (Prio 0, h1 -> h3 on Switch 2): Starts smoothly at 5 Mbps
    h3.popen('iperf -s -u -i 1')
    h1.popen('iperf -c 10.0.0.3 -u -b 5M -t 15') # fake video traffic with iperf (UDP, 5 Mbps)
    
    time.sleep(15)

    info("\n*** [DEMO] PHASE 2: CONGESTION! The Video requests 15 Mbps!\n")
    # The Video on h1 generates a peak towards h3
    h1.popen('iperf -c 10.0.0.3 -u -b 15M -t 20')
    
    time.sleep(25)

    info("\n*** [DEMO] PHASE 3: The Video peak is over. Waiting for automatic rollback...\n")

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
        http_link_config = {"bw": 10, "delay": "5ms", "max_queue_size":1000, "use_htb": True}

        # high latency, high bandwidth channel
        video_link_config = {"bw": 10, "delay": "1ms", "max_queue_size":1000, "use_htb": True}
        host_link_config = {"bw": 20, "delay": "1ms", "max_queue_size":1000, "use_htb": True} # Host links are faster to avoid bottlenecks at the edge of the network

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
        self.addLink("s1", "s2", **video_link_config) # Port 1: Priority 0 (Video)
        self.addLink("s1", "s2", **http_link_config) # Port 2: Priority 1 (HTTP)
        self.addLink("s1", "s3", **video_link_config) # Port 3: Priority 0 (Video)
        self.addLink("s1", "s3", **http_link_config) # Port 4: Priority 1 (HTTP)

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
    # h1, h2, h3, h4, h5 = net.get('h1','h2','h3','h4','h5')

    # stream a video from host 1 to host 5
    # h3.cmd("ffmpeg -re -stream_loop -1 -i /tmp/input_video.mp4 -c copy -f mpegts udp://10.0.0.5:7777 &")
    # h5.cmd('ffplay -nodisp -i udp://@:1234 &')
    # h5.cmd('ffmpeg -v info -i "udp://10.0.0.5:1234?fifo_size=0&overrun_nonfatal=1" -f null - &')

    # h1.cmd('ffmpeg -re -i input_video.mp4 -c:v copy -f mpegts "udp://10.0.0.5:1234?pkt_size=1316" &')

    # this should send the video received from h5 to the host machine
    # h5.cmd("socat UDP4-RECV:1234,fork UDP4-SEND:10.0.2.2:7777 &")


    # Simulation of traffic patterns and congestion scenarios
    t2 = threading.Thread(target=demo_orchestrator, args=(net,))
    t2.start()

    # automatically cut one of the links between s1 and s2 after 20 seconds
    t1 = threading.Thread(target=cut_link, args=(net, 20))
    t1.start()

    CLI(net)
    net.stop()
