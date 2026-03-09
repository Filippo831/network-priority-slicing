# panettone-imbibito

Networking 2 University of Trento project.

# Project: Network Slice Setup Optimization

- GOAL: to enable RYU SDN controller to slice the network and then to dynamically re-allocate services in order to maintain desired QoS.
- Example 1: migrate a server to maximize throughput via northbound script.
- Example 2: migrate a server to minimize delay via northbound script.
- Suggestion: include environmental changes via script (e.g. after 30 sec. A link goes down or new traffic is introduced in the network).

Keywords:
- Network Slicing
- RYU SDN Controller
- QoS
- Dynamic Network Traffic

# Priority-Based SDN Controller

A Ryu-based OpenFlow 1.3 controller that implements **Priority-Based Slicing** and **Adaptive Path Discovery**. This application segregates network traffic into virtual slices and dynamically learns inter-switch routes.

## Core Functionality

### 1. Priority-Based Slicing
Traffic is segregated by mapping Host IPs to specific **Priority Levels**. Switches are configured with a `router_links_priorities` map that dictates which physical ports belong to which slice. A host's traffic is primarily restricted to its designated priority ports, ensuring isolation.

### 2. Static Host Mapping
The controller maintains a hardcoded "Source of Truth" (`switch_hosts`) defining the exact location (Switch DPID and Port) of every host. Traffic from unknown hosts is ignored to maintain network integrity.

### 3. Dynamic Path Learning
While host locations are static, the paths between switches are learned on the fly:
* When a packet arrives, the controller records the `in_port` as the return path to the source switch for that specific priority.
* This populates `self.switch_priority_to_port`, allowing future traffic to bypass the discovery phase.

### 4. Adaptive Discovery & Escalation
If a route is unknown, the controller employs an **Escalation Logic**:
1. **Slice Discovery:** It floods the packet only to ports within the host's assigned priority level.
2. **Priority Escalation:** If no ports exist for that priority on a specific switch, it incrementally checks higher priority levels until a valid output port is found.
3. **Fallback:** Defaults to a standard flood only if all priority-specific searches fail.

### 5. Flow-Level Optimization
Upon determining a path, the controller installs an **OFPFlowMod** in the switch hardware. Subsequent packets in that flow (e.g., video streams) are forwarded at line rate without controller intervention.

### 6. Preemption Mechanism
To guarantee Service Level Agreements (SLAs) for Premium traffic (Priority 0), the system implements a closed-loop Quality of Service (QoS) monitoring and preemption mechanism:
1. **Hard Preemption:** If priority-0-traffic exceeds a critical bandwidth threshold (e.g., during a video bitrate spike), the controller intervenes. Rather than modifying OpenFlow routing paths, it directly manipulates the underlying Open vSwitch hardware queues (HTB) using Linux Traffic Control (tc).
2. **Resource Re-allocation:**  Bandwidth is dynamically "stolen" from the Best Effort slice (Priority 1) and reassigned to the Video slice. This expands the physical capacity of the high-priority link on the fly, preventing packet loss and preserving service fluidity.
3. **Elastic Rollback:** Once the traffic spike subsides and bandwidth usage drops below a safe threshold, the controller automatically restores the original queue limits, returning all network slices to their baseline physical configuration.




## usage

download the video that is used as test
```
wget https://archive.org/download/Rick_Astley_Never_Gonna_Give_You_Up/Rick_Astley_Never_Gonna_Give_You_Up.mp4 > input_video.mp4
```

start the controller
```
ryu-manager --observe-links controller.py monitor.py
```

build the topology
```
sudo python3 topology.py
```

# todo
## future implementations
- demo with video streaming on the link that will be cut to show the routing change to a working link

