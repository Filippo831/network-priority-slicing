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

# todo
## fixes
- check if the forwarding logic is correct
- understand if the packet takes the right route

## future implementation
- simulate a break in one of the links using a thread in topology.py
- when forwarding check if there is a channel that satisfies the priority requirements, if use another link (if the host priority value is too low, use the lowest priority value present in the links, if the priority value is too high, use the highest priority value present in the links)

## run
build the topology
```
sudo python3 topology.py
```

start the controller
```
ryu-manager --observe-links routing_controller.py
```
