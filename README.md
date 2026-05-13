# Network priority slicing

## Table of contents
- [Overview](#overview)
- [Structure](#structure)
- [Features](#features)
- [Getting started](#getting-started)
- [Test cases](#test-cases)
- [Team](#team)


## Overview
A Ryu-based OpenFlow 1.3 controller that implements **Priority-Based Slicing**, **Adaptive Path Discovery** and **QoS management**. 

## Structure
```
.
├── tests_output/       # store all the intermediate expected routing table and graph for testing
├── configurations/     # configurations of the priority for the tests and manual run
├── config.py           # read the configuration files
├── controller.py       # controller script entry point
├── flow_manager.py     # module for managing the flow rules and routing tables
├── graph.py            # module for maintaining the topology graph and performing path calculations
├── monitor.py          # module for monitoring the network state and triggering preemption
├── qos.py              # module for managing the QoS and preemption mechanism
├── README.md
├── test_scenarios.py   # test cases
└── topology.py         # manual topology creation script
```


## Features

### 1. Priority-Based Slicing
Every host and every port interconnecting the switches has a priority level that defines the flow of the packet depending on the priority level. The priorities is defined in the *\_\_init\_\_()* function inside [controller.py](https://github.com/Filippo831/network-priority-slicing/blob/main/controller.py). The packets will have the same priority level as the priority of the host sending that packet and they can travel only on links with the same priority or lower. If the priority doesn't match the closest lower priority is chosen, otherwise if the host priority is lower than all the links, the link with the lowest priority will be chosen.

### 2. Dynamic Path Learning
Using the python library [netowrkx](https://networkx.org/en/) a graph of the topology is kept including the priority level of the links to use graph functions to find the shortest path to the destination. Furthermore a custom routing table (*switch_priority_to_port*) is maintained to map each switch and priority level to the corresponding output port. This allows for efficient packet forwarding based on the priority constraints.

### 3. Failure handling
Upon link failure, the controller detects the event and updates the topology graph accordingly. It then recalculates optimal paths for affected flows, ensuring that traffic is rerouted through available links while respecting priority constraints. This dynamic adaptation minimizes disruption and maintains service continuity even in the face of network issues.

### 4. Preemption Mechanism
To guarantee Service Level Agreements (SLAs) for Premium traffic (Priority 0), the system implements a closed-loop Quality of Service (QoS) monitoring and preemption mechanism:
1. **Hard Preemption:** If priority-0-traffic exceeds a critical bandwidth threshold (e.g., during a video bitrate spike), the controller intervenes. Rather than modifying OpenFlow routing paths, it directly manipulates the underlying Open vSwitch hardware queues (HTB) using Linux Traffic Control (tc).
2. **Resource Re-allocation:**  Bandwidth is dynamically "stolen" from the Best Effort slice (Priority 1) and reassigned to the Video slice. This expands the physical capacity of the high-priority link on the fly, preventing packet loss and preserving service fluidity.
3. **Elastic Rollback:** Once the traffic spike subsides and bandwidth usage drops below a safe threshold, the controller automatically restores the original queue limits, returning all network slices to their baseline physical configuration.




## Getting started
#### Clone the repository
```
git clone https://github.com/Filippo831/network-priority-slicing.git
cd network-priority-slicing
```
#### Download requirements
```
pip install networkx 
```

<!-- ##### Download the video that is used as test and rename it -->
<!-- ``` -->
<!-- wget https://archive.org/download/Rick_Astley_Never_Gonna_Give_You_Up/Rick_Astley_Never_Gonna_Give_You_Up.mp4 -->
<!-- mv Rick_Astley_Never_Gonna_Give_You_Up.mp4 input_video.mp4 -->
<!-- ``` -->

#### Check if the environment is working by executing these lines

##### 1. Starting our custom controller
```
ryu-manager --observe-links controller.py monitor.py
```

##### 2. Creation of a basic topology and execution of some tests
```
sudo python3 topology.py
```

## Test cases
To run the test cases, execute this command
```
$ sudo -E python3 -m unittest
```
### Test case #1
```
h1                     h3
 │                     │ 
 └──┬──┐eth1 eth1┌──┬──┘ 
    │s1│=========│s2│    
 ┌──┴──┘eth2 eth2└──┴──┐ 
 │                     │ 
h2                     h4
```
#### Setup
| Priority | Hosts | Links |
| --- | --- | --- |
| 0 | `h1`, `h3` | `s1-eth1<->s2-eth1` |
| 1 | `h2`, `h4` | `s1-eth2<->s2-eth2` |

#### Scenario
##### Start (Baseline Traffic)
- **h1 <-> h3:** Traffic flows through the primary high-priority link (Priority 0) directly connecting switch `s1` and switch `s2` (`s1-eth1 <-> s2-eth1`).

##### Link Failure & Priority Degradation
- **s1-eth1 <-> s2-eth1 Link Failure:** After 10 seconds, the primary Priority 0 link between `s1` and `s2` is physically severed.
- **Action:** The Controller immediately detects the link down event and updates its internal topology graph. Since the optimal Priority 0 path is no longer available, the routing algorithm performs a graceful degradation. The `h1 <-> h3` traffic is dynamically rerouted through the backup link with the closest lower priority (`s1-eth2 <-> s2-eth2`, Priority 1). This ensures uninterrupted connectivity by falling back to the Best Effort network slice.

### Test case #2
<!-- ![Network design](./assets/network_design.md) -->
```
h5                                    h3
 │                                    │ 
 └──┬──┐eth3  eth1┌──┐eth1  eth1┌──┬──┘ 
    │s3│==========│s1│==========│s2│    
 ┌──┴──┘eth4  eth2└┬┬┘eth2  eth2└──┴──┐ 
 │                 ││                 │ 
h6                ┌┘└┐                h4
                  │  │                 
                 h1  h2
```

#### Setup 
##### Hosts
| Priority | Hosts | Links |
| --- | --- | --- |
| 0 | `h1`, `h3`, `h5` | `s1-eth1<->s2-eth1`; `s1-eth3<->s3-eth1`|
| 1 | `h2`, `h4`, `h6` | `s1-eth2<->s2-eth2`; `s1-eth4<->s3-eth2`|

#### Scenario
##### Start (Baseline Traffic)
- **h1 -> h3:** 8 Mbps on the Video slice (Priority 0).
- **h2 -> h4:** 8 Mbps on the Best Effort slice (Priority 1).
- Both streams fit perfectly within the default 10 Mbps physical limits of their respective links.

##### Bitrate Spike & Preemption Mechanism
- **h1 -> h3 (Spike):** The bitrate of the video stream suddenly spikes to 15 Mbps, exceeding the maximum 10 Mbps hardware capacity of the Priority 0 link.
- **Action:** The SDN Controller detects the congestion (bandwidth usage > 8.5 Mbps) and dynamically triggers the **Egress Traffic Shaping**. It reallocates bandwidth by throttling the Best Effort slice down to 5 Mbps, while expanding the Video slice to 15 Mbps. This guarantees that high-priority video traffic flows smoothly without packet loss during the spike.

##### Link Failure & Rerouting
- **s1-eth3 <-> s3-eth1 Link Failure:** The primary link between switch `s1` and switch `s3` is physically severed while the network is congested.
- **Action:** The Controller detects the topological change and recalculates the shortest paths. The priority 0 traffic that was supposed to flow through the failed link is immediately rerouted through the backup link with the closest lower priority (Priority 1), avoiding service downtime.

##### Elastic Rollback
- **End of Spike:** The video stream spike ends, and the `h1 -> h3` traffic drops back to its normal 8 Mbps baseline.
- **Action:** The Controller's Monitor component detects that the bandwidth utilization on the Video slice has dropped below the safe threshold (< 6.0 Mbps). It executes a Rollback operation, automatically restoring the original 10 Mbps hardware limits for both the Video and Best Effort slices, returning the network to its initial state.

### Test case #3
```
              ┌──h1       
           ┌──┤           
           │s1│           
      eth2/└──┘\eth1      
         /      \         
        /        \        
   eth2/          \eth1   
    ┌──┐          ┌──┐    
h3──┤s3├──────────┤s2├──h2
    └──┘eth1  eth2└──┘    
```
#### Setup 
###### Hosts
| Priority | Hosts | Links |
| --- | --- | --- |
| 0 | `h1`, `h2`, `h3` | `s1-eth1<->s2-eth1`; `s1-eth1<->s2-eth1`; `s1-eth2<->s3-eth2`|

#### Scenario
##### Start (Baseline Traffic)
- **h1 <-> h2:** Traffic flows through the shortest, direct link between switch `s1` and switch `s2` (`s1-eth1 <-> s2-eth1`).

##### Link Failure & Multi-Hop Rerouting
- **s1-eth1 <-> s2-eth1 Link Failure:** After 10 seconds, the direct link connecting `s1` and `s2` fails, completely breaking the shortest path.
- **Action:** The Controller detects the failure and updates the global topology graph. Recognizing that a direct connection is no longer possible, the routing algorithm recalculates the shortest path across the broader network ring. The `h1 <-> h2` traffic is successfully rerouted to take the alternative multi-hop path, flowing first through switch `s3` (`s1-eth2 <-> s3-eth2`) and then reaching its destination (`s3-eth1 <-> s2-eth1`). This demonstrates the system's resilience and ability to handle complex, indirect failover scenarios.

## Team
[![Tommaso Castagnaro](https://badgen.net/badge/icon/Tommaso%20Castagnaro/e88127?icon=github&label&labelColor=000)](https://github.com/tommyc03)
[![Luca Fossa Crescini](https://badgen.net/badge/icon/Luca%20Fossa%20Crescini/8ed827?icon=github&label&labelColor=000)](https://github.com/luca531)
[![Filippo Arduini](https://badgen.net/badge/icon/Filippo%20Arduini/c8c110?icon=github&label&labelColor=000)](https://github.com/tommyc03)
- **Tommaso Castagnaro**: Preemption mechanism
- **Luca Fossa Crescini**: Graph and failure handling
- **Filippo Arduini**: dynamic path learning, testing
