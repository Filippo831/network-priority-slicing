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
ryu-manager fast_slice.py
```


# notes
- gui topology sits at this directory
/usr/lib/python3/dist-packages/ryu/app/gui_topology/gui_topology.py
