# K8s-Distributed-Scheduler

This project implements a distributed scheudler that runs a distributed consensus scheduling algorithm.

## Installation and Usage

After installing a Kubernetes Cluster.

Run 

```bash
python src/server/server.py
```
on the master node. The created server process will create the schedulers on the worker nodes and run the scheduling process automatically.

## Folder Structure
    .
    ├── src                           # The code for the distributed scheduler
    │   ├── client          
    │   │   ├── client.py             # Scheduling Logic includes the distributed implementation of consensus
            ├── MyOwnPeer2PeerNode.py # The TCP/IP server inside scheduler
            └── ...
    │   ├── server
    │   │   ├── server.py             # Controls scheduling process
        │   ├── MyOwnPeer2PeerNode.py # The TCP/IP server inside server
        │   └── ...          
    │   ├── deployments               # Contains all K8s Deployment files
    │   └── docker-compose.yaml       # Build scheudler container image         
    │
    ├── images                        # The images used in report
    ├── plotting                      # Python scripts to generate images from logs
    ├── logs                    
    ├── cluster_script                # Bash scripts for different purposes (e.g. create a K8s cluster)
