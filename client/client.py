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
import threading

from MyOwnPeer2PeerNode import MyOwnPeer2PeerNode

DOCKER_SOCKET_URL = 'unix://var/run/docker.sock'
DEFAULT_PORT = 10001
is_node_alive = False

def start_client(node,cond,run_lock):
    #---------- Establishing Connections ----------
    SERVER_SERVICE_IP = socket.gethostbyname('caelum-102')
    node.connect_with_node(SERVER_SERVICE_IP, DEFAULT_PORT)
    # Wait for server message
    cond.acquire()
    while True:
        if len(node.message_received)!=0:
            break
        print("[Client] Waiting for server message...")
        val = cond.wait()
        if val:
            continue
        else:
            break
    cond.release()

    # while len(node.message_received)==0:
    #     print("[Client] Waiting for server message...")
    #     time.sleep(5)

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

    #Logging
    local_comp_time_list = []
    msg_ex_xy_time_list = []
    msg_ex_z_time_list = []

    local_comp_cpu_list = []
    local_comp_mem_list = []
    local_comp_disk_list = []
    local_comp_net_in_list = []
    local_comp_net_out_list = []

    msg_ex_cpu_list = []
    msg_ex_mem_list = []
    msg_ex_disk_list = []
    msg_ex_net_in_list = []
    msg_ex_net_out_list = []



    #---------- Consensus Algorithm ----------
    # Send consensus start message to server
    node.send_to_nodes(str({"start_consensus":None}))
    while node.start_consensus == False:
        time.sleep(2)
    print("[Client] start consensus")
    while i < max_iter and can_terminate == 0 and not node.new_trial:
        
        #---------- Logging ----------
        net_stat = psutil.net_io_counters()
        net_in_1 = net_stat.bytes_recv
        net_out_1 = net_stat.bytes_sent

        local_comp_time = 0
        msg_ex_xy_time = 0
        msg_ex_z_time = 0

        local_comp_cpu = 0
        local_comp_mem = 0
        local_comp_disk = 0
        local_comp_net_in = 0
        local_comp_net_out = 0

        msg_ex_cpu = 0
        msg_ex_mem = 0
        msg_ex_disk = 0
        msg_ex_net_in = 0
        msg_ex_net_out = 0

        local_comp1_time_start = time.time()
        #---------- End Logging ----------


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

        #---------- Logging ----------
        local_comp_time += (time.time()-local_comp1_time_start)
        local_comp_cpu = psutil.cpu_percent(interval=None,percpu=True)
        local_comp_mem = psutil.virtual_memory().percent
        local_comp_disk = psutil.disk_usage('/').percent
        # print("Local Computation: ", psutil.cpu_percent(interval=None,percpu=True))
        # print("Local Computation Memory usage: ", psutil.virtual_memory().percent)
        # print("Local Computation Disk usage: ", psutil.disk_usage('/').percent)
        net_stat = psutil.net_io_counters()
        net_in_2 = net_stat.bytes_recv
        net_out_2 = net_stat.bytes_sent
        net_in = round((net_in_2 - net_in_1) / 1024, 3)
        net_out = round((net_out_2 - net_out_1) / 1024, 3)
        local_comp_net_in = net_in
        local_comp_net_out = net_out
        # print(f"Local Computation net-usage:\nIN: {net_in} KB/s, OUT: {net_out} KB/s")
        #---------- End Logging ----------
        
        
        
        #---------- Logging ----------
        net_stat = psutil.net_io_counters()
        net_in_1 = net_stat.bytes_recv
        net_out_1 = net_stat.bytes_sent
        msg_ex_xy_time_start = time.time()
        #---------- End Logging ----------

        node.send_to_nodes(str({"exchange_xy":{i:[bar_xd_k,bar_yd_k]}}), exclude=[server_addr])

        try:
            # print("[Main thread] acquiring lock....")
            cond.acquire()
            while True:
                if i in node.xy_storage and len(node.xy_storage[i]) == num_in_neigh:
                    # print("[Main thread] condition satisfy....")
                    break
               
                # print("[Main thread] Not yet received all xy message, wait for 30 sec..")
                # wait with a maximum timeout of 10 sec

                val = cond.wait(30)
                if val:
                    # print("[Main thread] notification received all xy message received.")
                    continue
                else:
                    # print("[Main thread] xy message waiting timeout...")
                    break
            # print("[Main thread] realease lock....")       
            cond.release()
            # while True and not node.new_trial:
            #     if i in node.xy_storage and len(node.xy_storage[i]) == num_in_neigh:
            #         # print("All message at timestamp ",i," receievd: ",node.xy_storage[i])
            #         break

            #---------- Logging ----------
            msg_ex_xy_time = (time.time()-msg_ex_xy_time_start)
            local_comp2_time_start = time.time()
            #---------- End Logging ----------

            if not is_self_connected:
                bar_xd_k = 0
                bar_yd_k = 0
            for [x,y] in node.xy_storage[i]:
                bar_xd_k += float(x)
                bar_yd_k += float(y)
            # Calculate z locally
            bar_zd_k = bar_xd_k / bar_yd_k 

            #---------- Logging ----------
            local_comp_time += (time.time()-local_comp2_time_start)
            msg_ex_z_time_start = time.time()
            #---------- End Logging ----------

            # Send z to all out nieghbours
            node.send_to_nodes(str({"exchange_z":{i:bar_zd_k}}), exclude=[server_addr])
            #Collect all z from in neighbours
            # for m in node.message_received:
            
            
            # print("[Main thread] acquiring lock....")
            cond.acquire()
            while True:
                if i in node.z_storage and len(node.z_storage[i]) == num_in_neigh:
                    break
                val = cond.wait(30)
                if val:
                    continue
                else:
                    break
            cond.release()

            # while True and not node.new_trial:
            #     if i in node.z_storage and len(node.z_storage[i]) == num_in_neigh:
            #         # print("All message at timestamp ",i," receievd: ",node.z_storage[i])
            #         break

            #---------- Logging ----------
            msg_ex_z_time = (time.time()-msg_ex_z_time_start)
            msg_ex_cpu = psutil.cpu_percent(interval=None,percpu=True)
            msg_ex_mem = psutil.virtual_memory().percent
            msg_ex_disk = psutil.disk_usage('/').percent
            # print("Message Exchange: ", psutil.cpu_percent(interval=None,percpu=True))
            # print("Message Exchange Memory usage: ", psutil.virtual_memory().percent)
            # print("Message Exchange Disk usage: ", psutil.disk_usage('/').percent)
            net_stat = psutil.net_io_counters()
            net_in_2 = net_stat.bytes_recv
            net_out_2 = net_stat.bytes_sent
            net_in = round((net_in_2 - net_in_1) / 1024, 3)
            net_out = round((net_out_2 - net_out_1) / 1024, 3)
            msg_ex_net_in = net_in
            msg_ex_net_out = net_out
            # print(f"Message Exchange net-usage:\nIN: {net_in} KB/s, OUT: {net_out} KB/s")
            #---------- End Logging ----------

            
            local_comp_time_start = time.time()
            B = np.asarray(node.z_storage[i])
            if is_self_connected:
                B = np.append(B,bar_zd_k)
            M = np.nanmax(B)
            b_min = B[B!=0]
            if b_min.size==0:
                m = 0
            else:
                m = np.nanmin(b_min)
            local_comp_time += (time.time()-local_comp_time_start)
            
        
            # Send iteration result to server
            node.send_to_nodes(str({"client_msg":[HOSTNAME,i,flag,bar_zd_k]}))

            
            #
            local_comp_time_list.append(local_comp_time)
            msg_ex_xy_time_list.append(msg_ex_xy_time)
            msg_ex_z_time_list.append(msg_ex_z_time)

            local_comp_cpu_list.append(local_comp_cpu)
            local_comp_mem_list.append(local_comp_mem)
            local_comp_disk_list.append(local_comp_disk)
            local_comp_net_in_list.append(local_comp_net_in)
            local_comp_net_out_list.append(local_comp_net_out)

            msg_ex_cpu_list.append(msg_ex_cpu)
            msg_ex_mem_list.append(msg_ex_mem)
            msg_ex_disk_list.append(msg_ex_disk)
            msg_ex_net_in_list.append(msg_ex_net_in)
            msg_ex_net_out_list.append(msg_ex_net_out)
            if i % 20 == 0:
                print("Iteration: ", i)
                print("Local computation time: ", local_comp_time)
                print("Exchange message time (xy): ", msg_ex_xy_time)
                print("Exchange message time (z): ", msg_ex_z_time)

                print("Local Computation (cpu): ", local_comp_cpu)
                print("Local Computation (mem): ", local_comp_mem)
                print("Local Computation (disk): ", local_comp_disk)
                print("Local Computation (net_in): ", local_comp_net_in)
                print("Local Computation (net_out): ", local_comp_net_out)

                print("Exchange message (cpu): ", msg_ex_cpu)
                print("Exchange message (mem): ", msg_ex_mem)
                print("Exchange message (disk): ", msg_ex_disk)
                print("Exchange message (net_in): ", msg_ex_net_in)
                print("Exchange message (net_out): ", msg_ex_net_out)

            i = i + 1
        except Exception as e:
            if node.new_trial:
                print("Exception Occured: ", e)

    return local_comp_time_list, msg_ex_xy_time_list, msg_ex_z_time_list, local_comp_cpu_list, local_comp_mem_list, local_comp_disk_list, local_comp_net_in_list, local_comp_net_out_list, msg_ex_cpu_list, msg_ex_mem_list, msg_ex_disk_list, msg_ex_net_in_list, msg_ex_net_out_list

if __name__ == "__main__":
    #---------- Client Initialisation ----------
    HOSTNAME = socket.gethostbyname(os.environ.get("HOSTNAME"))
    print(HOSTNAME)
    cond = threading.Condition()
    run_lock = threading.Condition()
    node = MyOwnPeer2PeerNode(HOSTNAME, DEFAULT_PORT, HOSTNAME, cond=cond, run_lock=run_lock)
    node.start()
    print("Number of cores in system", psutil.cpu_count())
    print("\nNumber of physical cores in system",)
    print("First CPU Usage: ", psutil.cpu_percent(interval=None,percpu=True))
    print("First Memory usage: ", psutil.virtual_memory().percent)
    print("First Disk usage: ", psutil.disk_usage('/').percent)
    
    while True:
        while node.new_trial:
            print("Waiting for reset")
            while not (len(node.nodes_inbound) <= 1 and len(node.nodes_outbound) <= 1):
                print("Not all nodes disconnected")
                print("Start of trial, number of inbound: ", len(node.nodes_inbound))
                print("Start of trial, number of outbound: ",len(node.nodes_outbound))
                print(not (len(node.nodes_inbound) <= 1 and len(node.nodes_outbound) <= 1))
                time.sleep(5)
            # Tell server client has successfully reset
            node.send_to_nodes(str({"client_reset":None}))
            print("A new trial has begun")
            run_lock.acquire()
            node.new_trial = False
            local_comp_time_list, msg_ex_xy_time_list, msg_ex_z_time_list, local_comp_cpu_list, local_comp_mem_list, local_comp_disk_list, local_comp_net_in_list, local_comp_net_out_list, msg_ex_cpu_list, msg_ex_mem_list, msg_ex_disk_list, msg_ex_net_in_list, msg_ex_net_out_list = start_client(node,cond,run_lock)
            print("Function returned")
            run_lock.release()
            node.send_to_nodes(str({"client_result":[HOSTNAME,local_comp_time_list, msg_ex_xy_time_list, msg_ex_z_time_list, local_comp_cpu_list, local_comp_mem_list, local_comp_disk_list, local_comp_net_in_list, local_comp_net_out_list, msg_ex_cpu_list, msg_ex_mem_list, msg_ex_disk_list, msg_ex_net_in_list, msg_ex_net_out_list]}))

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

    
        

