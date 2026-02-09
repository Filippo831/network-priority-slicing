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




## usage

download the video that is used as test
```
curl https://archive.org/download/Rick_Astley_Never_Gonna_Give_You_Up/Rick_Astley_Never_Gonna_Give_You_Up.mp4 > input_video.mp4
```

build the topology
```
sudo python3 topology.py
```

start the controller
```
ryu-manager controller.py monitor.py
```


# todo
## future implementations
- create an issue in the video streaming link and change the priority to maintain the qos
- 

