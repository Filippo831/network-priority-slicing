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

## run
build the topology
```
sudo python3 topology.py
```

start the controller
```
ryu-manager monitor_controller.py routing_controller.py
```


# notes
## implementation
- create fixed ethernet connection in each switch that are marked with a priority number
- create a list of host with different priorities
- when a packets enters the switch, somehow make it automatically decide which port to use and check if it's using a port with the right priority number

## testing
- create a break in one of the high priority link
- use a lower priority, (lowering the other priorities by 1 to keep the high priority connection free??)
