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

from MyOwnPeer2PeerNode import MyOwnPeer2PeerNode

DOCKER_SOCKET_URL = 'unix://var/run/docker.sock'
DEFAULT_PORT = 10001
is_node_alive = False

def start_client(node):
    #Start client node
    
    # node = MyOwnPeer2PeerNode(HOSTIP, DEFAULT_PORT, HOSTIP)
    node.start()
    # print("os host name:", HOSTNAME)
    # print("socket host name:", socket.gethostname())
    # print("socket ip from os hostname:", socket.gethostbyname(HOSTNAME))
    # print("socket ip from socket hostname:", socket.gethostbyname(socket.gethostname()))

    #SERVER_SERVICE_IP: need to know before hand
    SERVER_SERVICE_IP = socket.gethostbyname('caelum-102')
    #TODO: Client connect to server
    node.connect_with_node(SERVER_SERVICE_IP, DEFAULT_PORT)
    
    # Wait for server message needs long time in k8s
    while len(node.message_received)==0:
        print("Waiting for server message")
        time.sleep(5)

    init = node.message_received[0]
    #Reset message buffer
    # node.message_received = []

    # Initialisation
    # Connecting outbound nodes
    is_self_connected = False
    num_out_neigh = 0
    for c in init["graph"][HOSTNAME]:
        node.connect_with_node(c, DEFAULT_PORT)
        num_out_neigh+=1
        if c == HOSTNAME:
            is_self_connected = True
    server_addr = init["server_addr"]
    node.connect_with_node(server_addr, DEFAULT_PORT)
    
    time.sleep(20)
    num_in_neigh = len(node.nodes_inbound)-1
    # print("In Bound Node: ",node.nodes_inbound)
    # print("Out Bound Node: ",node.nodes_outbound)
    #Variables
    max_iter = int(init["max_iter"])
    # max_iter = 300
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

    #Start running Consensus Loop
    node.send_to_nodes(str({"start_consensus":None}))
    while i < max_iter and can_terminate == 0:
        cal_time = time.time()
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

        #Exchange Parameters
        bar_xd_k = bar_xd_k * (1/num_out_neigh)
        bar_yd_k = bar_yd_k * (1/num_out_neigh)
        
        if i < 3:
            print("Calculation time:", time.time()-cal_time)

        node.send_to_nodes(str({"exchange_xy":{i:[bar_xd_k,bar_yd_k]}}), exclude=[server_addr])
        
        wait_xy_time = time.time()

        while True:
            # print("Currently at iteraition: ",i)
            # if i in node.xy_storage:
            #     print(node.xy_storage[i])
            # print("Number of in-neighbours", num_in_neigh)
            # time.sleep(10)
            if i in node.xy_storage and len(node.xy_storage[i]) == num_in_neigh:
                # print("All message at timestamp ",i," receievd: ",node.xy_storage[i])
                break

        if i < 3:
            print("wait_xy time:", time.time()-wait_xy_time)

        if not is_self_connected:
            bar_xd_k = 0
            bar_yd_k = 0

        for [x,y] in node.xy_storage[i]:
            bar_xd_k += float(x)
            bar_yd_k += float(y)

        #Calculate z locally
        bar_zd_k = bar_xd_k / bar_yd_k 
        
        #Send z to all out nieghbours
        node.send_to_nodes(str({"exchange_z":{i:bar_zd_k}}), exclude=[server_addr])

        #Collect all z from in neighbours
        # for m in node.message_received:
        wait_z_time = time.time()
        while True:
            if i in node.z_storage and len(node.z_storage[i]) == num_in_neigh:
                # print("All message at timestamp ",i," receievd: ",node.z_storage[i])
                break
                
        if i < 3:
            print("wait_z time:", time.time()-wait_z_time)
        
        B = np.asarray(node.z_storage[i])
        if is_self_connected:
            B = np.append(B,bar_zd_k)
        M = np.nanmax(B)
        b_min = B[B!=0]
        if b_min.size==0:
            m = 0
        else:
            m = np.nanmin(b_min)

        # print(bar_zd_k)

        # print("send to server at the iteration: ", i)
        node.send_to_nodes(str({"client_msg":[HOSTNAME,i,flag,bar_zd_k]}))
            # can_terminate = 1
            # print(i)
            # print(bar_zd_k)

        i = i + 1


    #TODO: File "./client.py", line 25, in start_client
# client_1  |     init = ast.literal_eval(node.message_received[0])
# client_1  | IndexError: list index out of range

#TODO: cannot connect to self



if __name__ == "__main__":
    HOSTNAME = os.environ.get("HOSTNAME")
    # HOSTIP = socket.gethostbyname(HOSTNAME)
    HOSTNAME = socket.gethostbyname(HOSTNAME)
    print(HOSTNAME)
    node = MyOwnPeer2PeerNode(HOSTNAME, DEFAULT_PORT, HOSTNAME)
    start_client(node)
    while node.new_iteration:
        node.new_iteration = False
        node.stop()
        time.sleep(20)
        HOSTNAME = os.environ.get("HOSTNAME")
        # HOSTIP = socket.gethostbyname(HOSTNAME)
        HOSTNAME = socket.gethostbyname(HOSTNAME)
        print(HOSTNAME)
        node = MyOwnPeer2PeerNode(HOSTNAME, DEFAULT_PORT, HOSTNAME)
        start_client(node)

    
        

