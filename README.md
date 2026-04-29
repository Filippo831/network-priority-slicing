# Network priority slicing

## Table of contents
- [Overview](#overview)
- [Features](#features)
- [Getting started](#getting-started)
- [Test case](#test-case)


## Overview
A Ryu-based OpenFlow 1.3 controller that implements **Priority-Based Slicing**, **Adaptive Path Discovery** and **QoS management**. 


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
To run the test cases, run this command
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
| 0 | h1, h3 | s1-eth1<->s2-eth1 |
| 1 | h2, h4 | s1-eth2<->s2-eth2 |

#### Scenario
##### After 10 seconds - link failure
- s1-eth1<->s2-eth1 link failure: the link between s1 and s2 fails.

- Controller detects the failure and updates the topology graph accordingly. In this case the traffic between h1 and h3 is rerouted through s1-eth2<->s2-eth2, which is the link with the closest lower priority.

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
| 0 | h1, h3, h5 | s1-eth1<->s2-eth1; s1-eth3<->s3-eth1|
| 1 | h2, h4, h6 | s1-eth2<->s2-eth2; s1-eth4<->s3-eth2|

#### Scenario
##### Start
- h1 -> h3: 5 Mbps priority 0.
- h2 -> h4: 8 Mbps priority 1.
##### After 15 seconds - preemption mechanism
- h1 -> h3: 15Mbps: bitrate of the video stream from h1 to h3 exceeds the maximum bitrate available.

- Controller detects the increase in bandwidth usage and dynamically reallocates bandwidth from the Best Effort slice (Priority 1) to the Video slice (Priority 0). This ensures that the high-priority traffic continues to flow smoothly without packet loss, even during the spike in demand.
##### After 20 seconds - link failure
- s1-eth3<->s3-eth1 link failure: the link between s1 and s2 fails.

- Controller detects the failure and updates the topology graph accordingly. In this case the priority 0 traffic that were supposed to flow through the failed link will be rerouted through the link with the closer lower priority the link with priority 1.
##### After 35 seconds - elastic rollback
- Close connection h1 -> h3: the connection from h1 to h3 is closed.

- Controller detects the change in traffic patterns and restores the original bandwidth allocation for the Best Effort slice (Priority 1), ensuring that all network slices return to their baseline physical configuration.

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
| 0 | h1, h3, h5 | s1-eth1<->s2-eth1; s1-eth1<->s2-eth1; s1-eth2<->s3-eth2|

#### Scenario
##### After 10 seconds - link failure
- s1-eth1<->s2-eth1 link failure: link between s1 and s2 fails.

- Controller detects the failure and updates the topology graph accordingly. In this case the traffic between h1 and h2 is rerouted through s1-eth2<->s3-eth2 and s3-eth1<->s2-eth1.