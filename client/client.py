import sys
import time
import argparse
import socket
from docker import Client
import json
import os
import ast
import math
import numpy as np
import psutil

from MyOwnPeer2PeerNode import MyOwnPeer2PeerNode

DOCKER_SOCKET_URL = 'unix://var/run/docker.sock'
DEFAULT_PORT = 10001
is_node_alive = False

def start_client(node):
    #---------- Establishing Connections ----------
    SERVER_SERVICE_IP = socket.gethostbyname('caelum-102')
    node.connect_with_node(SERVER_SERVICE_IP, DEFAULT_PORT)
    # Wait for server message
    while len(node.message_received)==0:
        print("Waiting for server message")
        time.sleep(5)
    init = node.message_received[0]
    # Connecting outbound nodes
    is_self_connected = False
    num_out_neigh = 0
    for c in init["graph"][HOSTNAME]:
        node.connect_with_node(c, DEFAULT_PORT)
        num_out_neigh+=1
        if c == HOSTNAME:
            is_self_connected = True
    server_addr = init["server_addr"]
    # node.connect_with_node(server_addr, DEFAULT_PORT)
    # TODO: check if sleep is necessary here
    time.sleep(20)

    #---------- Parameter Initialisation ----------
    num_in_neigh = len(node.nodes_inbound)-1
    max_iter = int(init["max_iter"])
    epsilon = float(init["epsilon"])
    bar_xd_k = float(init["workload"][HOSTNAME])
    bar_yd_k = float(init["capacity"][HOSTNAME])
    M = float(init["M"])
    m = float(init["m"])
    mod_factor = float(init["mod_factor"])
    flag = 0
    can_terminate = 0
    bar_zd_k = None
    i=0

    #---------- Consensus Algorithm ----------
    # Send consensus start message to server
    node.send_to_nodes(str({"start_consensus":None}))
    while i < max_iter and can_terminate == 0 and not node.new_trial:
        
        net_stat = psutil.net_io_counters()
        net_in_1 = net_stat.bytes_recv
        net_out_1 = net_stat.bytes_sent

        local_calc_time = 0
        exchange_xy_time = 0
        exchange_z_time = 0

        local_calc_time_start = time.time()
        if flag == 0:
            if i % mod_factor == 0 and i > 0:
                if M - m < epsilon:
                    prev_flag = flag
                    flag = 1
                    # print("\t -- DEBUG: Node ",j," satisfied contraint at time step ",i)
                    # if node_stats[j][0] == 0:
                    #     node_stats[j][0] = i
                    # #set the max only if was flipped - it is also
                    # #monotonically increasing hence at every check i will be
                    # #greater.
                    # if prev_flag == 0:
                    #     # change the node max timestep
                    #     node_stats[j][1] = i
                    #     # this counts as a flip, so advance it.
                    #     node_stats[j][2] = node_stats[j][2] + 1
                M = bar_zd_k
                m = bar_zd_k
        else:
            if M - m >= epsilon:
                # print("\t -- DEBUG: Node ",j," DO NOT satisfy the contraint at time step ",i)
                # flip the node - actual flips are counted in in the top loop
                flag = 0
        if not math.isnan(M) and not math.isnan(m):
            assert(M>= m or (abs(M - m) < epsilon))
        # Exchange Parameters
        bar_xd_k = bar_xd_k * (1/num_out_neigh)
        bar_yd_k = bar_yd_k * (1/num_out_neigh)
        local_calc_time += (time.time()-local_calc_time_start)
        print("Local Computation: ", psutil.cpu_percent(interval=None,percpu=True))
        print("Local Computation Memory usage: ", psutil.virtual_memory().percent)
        print("Local Computation Disk usage: ", psutil.disk_usage('/').percent)

        net_stat = psutil.net_io_counters()
        net_in_2 = net_stat.bytes_recv
        net_out_2 = net_stat.bytes_sent
        net_in = round((net_in_2 - net_in_1) / 1024, 3)
        net_out = round((net_out_2 - net_out_1) / 1024, 3)
        print(f"Local Computation net-usage:\nIN: {net_in} KB/s, OUT: {net_out} KB/s")
        
        
        net_stat = psutil.net_io_counters()
        net_in_1 = net_stat.bytes_recv
        net_out_1 = net_stat.bytes_sent

        exchange_xy_time_start = time.time()
        node.send_to_nodes(str({"exchange_xy":{i:[bar_xd_k,bar_yd_k]}}), exclude=[server_addr])
        while True:
            if i in node.xy_storage and len(node.xy_storage[i]) == num_in_neigh:
                # print("All message at timestamp ",i," receievd: ",node.xy_storage[i])
                break
        exchange_xy_time += (time.time()-exchange_xy_time_start)

        local_calc_time_start = time.time()
        if not is_self_connected:
            bar_xd_k = 0
            bar_yd_k = 0
        for [x,y] in node.xy_storage[i]:
            bar_xd_k += float(x)
            bar_yd_k += float(y)
        # Calculate z locally
        bar_zd_k = bar_xd_k / bar_yd_k 
        local_calc_time += (time.time()-local_calc_time_start)
 

      
        exchange_z_time_start = time.time()
        # Send z to all out nieghbours
        node.send_to_nodes(str({"exchange_z":{i:bar_zd_k}}), exclude=[server_addr])
        #Collect all z from in neighbours
        # for m in node.message_received:
        wait_z_time = time.time()
        while True:
            if i in node.z_storage and len(node.z_storage[i]) == num_in_neigh:
                # print("All message at timestamp ",i," receievd: ",node.z_storage[i])
                break
        exchange_z_time += (time.time()-exchange_z_time_start)
        print("Message Exchange: ", psutil.cpu_percent(interval=None,percpu=True))
        print("Message Exchange Memory usage: ", psutil.virtual_memory().percent)
        print("Message Exchange Disk usage: ", psutil.disk_usage('/').percent)

        net_stat = psutil.net_io_counters()
        net_in_2 = net_stat.bytes_recv
        net_out_2 = net_stat.bytes_sent
        net_in = round((net_in_2 - net_in_1) / 1024, 3)
        net_out = round((net_out_2 - net_out_1) / 1024, 3)
        print(f"Message Exchange net-usage:\nIN: {net_in} KB/s, OUT: {net_out} KB/s")

        
        local_calc_time_start = time.time()
        B = np.asarray(node.z_storage[i])
        if is_self_connected:
            B = np.append(B,bar_zd_k)
        M = np.nanmax(B)
        b_min = B[B!=0]
        if b_min.size==0:
            m = 0
        else:
            m = np.nanmin(b_min)
        local_calc_time += (time.time()-local_calc_time_start)
        
       
        # Send iteration result to server
        node.send_to_nodes(str({"client_msg":[HOSTNAME,i,flag,bar_zd_k]}))

        
        if i % 50 == 0:
            print("Iteration: ", i, "Local calculation time: ", local_calc_time, 
                "Exchange message time (xy): ", exchange_xy_time, "Exchange message time (z): ", exchange_z_time)

        i = i + 1

if __name__ == "__main__":
    #---------- Client Initialisation ----------
    HOSTNAME = socket.gethostbyname(os.environ.get("HOSTNAME"))
    print(HOSTNAME)
    node = MyOwnPeer2PeerNode(HOSTNAME, DEFAULT_PORT, HOSTNAME)
    node.start()
    print("Number of cores in system", psutil.cpu_count())
    print("\nNumber of physical cores in system",)
    print("First CPU Usage: ", psutil.cpu_percent(interval=None,percpu=True))
    print("First Memory usage: ", psutil.virtual_memory().percent)
    print("First Disk usage: ", psutil.disk_usage('/').percent)
    while True:
        time.sleep(5)
        while node.new_trial:
            print("Waiting for reset")
            while not (len(node.nodes_inbound) <= 1 and len(node.nodes_outbound) <= 1):
                print("Not all nodes disconnected")
                print("Start of trial, number of inbound: ", len(node.nodes_inbound))
                print("Start of trial, number of outbound: ",len(node.nodes_outbound))
                print(not (len(node.nodes_inbound) <= 1 and len(node.nodes_outbound) <= 1))
                time.sleep(5)
            print("A new trial has begun")
            node.new_trial = False
            start_client(node)

    # while node.new_trial:
    #     node.new_trial = False
    #     node.stop()
    #     time.sleep(20)
    #     HOSTNAME = os.environ.get("HOSTNAME")
    #     # HOSTIP = socket.gethostbyname(HOSTNAME)
    #     HOSTNAME = socket.gethostbyname(HOSTNAME)
    #     print(HOSTNAME)
    #     node = MyOwnPeer2PeerNode(HOSTNAME, DEFAULT_PORT, HOSTNAME)
    #     start_client(node)

    
        

