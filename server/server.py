from http import server
import sys
import time
import argparse
import subprocess
from docker import Client
import os
import numpy as np
import random
import urllib
import socket
import math
import json
from gen_graph import gen_graph
from gen_workload import gen_workload
from load_workload import load_workload
import copy
from ortools.linear_solver import pywraplp
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from MyOwnPeer2PeerNode import MyOwnPeer2PeerNode

DOCKER_SOCKET_URL = 'unix://var/run/docker.sock'
URL_REQUEST = 'https://v4.ident.me'
DEFAULT_PORT = 10001


def start_server(num_clients, server_node, max_iter=1000, workload_min=100,workload_max=1000,epsilon=1e-5,use_variable_capacities = 0):
    #---------- Establishing Connections ----------
    # Waiting for connection from client
    while len(server_node.client_hostname_list) < num_clients:
        print("Not yet Receieve all client")
        time.sleep(5)
    print("Client Hostnames: ", "[", len(server_node.client_hostname_list),"]",server_node.client_hostname_list)
    # Connect to all client
    for client in server_node.client_hostname_list:
        server_node.connect_with_node(client, DEFAULT_PORT)
    # Check connected clients
    assert(num_clients == len(server_node.client_hostname_list))
    #---------- Parameter Initialisation ----------
    server_node.param_init(max_iter)
    # Generate Graph
    print("Server Generating Graph....")
    AdjMatrix, diameter = gen_graph(num_clients,False)
    # Generate Workload
    x_0 = gen_workload(workload_min, workload_max, num_clients)
    # print("x_0:", np.transpose(x_0)[0])
    # Generate Capacity
    y_0=None
    if use_variable_capacities == 0:
        y_0 = np.ones((num_clients, 1))*1000
    else:
        #Half of the nodes have the capacity of 3 and half have 5
        y1 = 3 * np.ones((math.ceil(num_clients / 2), 1))
        y2 = 5 * np.ones((math.floor(num_clients / 2), 1))
        y_0 = np.concatenate((y1,y2)) 
    # print("y_0:", np.transpose(y_0)[0])
    # Generate max and min   
    M = x_0.max()
    m = x_0.min()
    # Generate mod factor
    max_delay = 0 # We assume no delay first
    mod_factor = (1 + max_delay) * diameter
    #---------- Create and Send Message ----------
    # Create Connection Message
    graph = {}
    for c in range(num_clients):
        out_nei = []
        for r in range(num_clients):
            if AdjMatrix[r][c] == 1.0:
                out_nei.append(server_node.client_hostname_list[r])
        graph[server_node.client_hostname_list[c]] = out_nei
    # Create Workload Message
    workload = {}
    for i in range(num_clients):
        workload[server_node.client_hostname_list[i]] = x_0[i][0]
    # Create Capacity Message
    capacity = {}
    for i in range(num_clients):
        capacity[server_node.client_hostname_list[i]] = y_0[i][0]
    # collect message
    msg={}
    msg["server_addr"] = HOSTNAME[:12]
    msg["max_iter"] = max_iter
    msg["epsilon"] = epsilon
    msg["graph"] = graph
    msg["workload"] = workload
    msg["capacity"] = capacity
    msg["M"] = M
    msg["m"] = m
    msg["mod_factor"] = mod_factor
    # Send message
    server_node.send_to_nodes(str({"server_msg":msg}))
    #---------- Record Consensus Status ----------
    print("[Consensus] Start")
    start_time = time.time()
    cur_iter = 0
    while True:
        count = 0
        count_one = 0
        for f in server_node.flag_storage[cur_iter].values():
            if f < 0:
                break
            elif f == 0:
                if time.time() - start_time > 180:
                    print("Something happened... exit current trial")
                    server_node.send_to_nodes(str({"stop":0}))
                    time.sleep(5)
                    return 0, None, None, None
                count+=1
            elif f==1:
                count+=1
                count_one+=1
            # print(server_node.flag_storage[cur_iter])
        if count == num_clients:
            if(cur_iter%10==0):
                print("[Consensus] Currently at iteration: ", cur_iter)
            cur_iter+=1
            if cur_iter == max_iter:
                print("[Consensus] Max Iteration Reached")
                break
        if count_one == num_clients:
            print("[Consensus] Consensus Reached")    
            break

    consensus_time = time.time() - server_node.start_consensus_time
    total_iteration = cur_iter-1
    print("[Consensus] Consensus takes %s seconds" % (consensus_time))
    print("[Consensus] Ending at iteration: ", total_iteration)
    print("[Consensus] All ratio ended at: ", json.dumps(server_node.z_storage[cur_iter-1]))
    print("[Consensus] End Consensus")
    # Close client node
    server_node.send_to_nodes(str({"stop":0}))
    # TODO: check if sleep is necessary here
    time.sleep(5)
    # server_node.stop()
    # is_complete = subprocess.check_output(["kubectl","delete", "deployments/client"])
    return 1, consensus_time, total_iteration, diameter

    # ################Job/Task Distribute#################
    # print("---Start Job Assigning---")
    # start_job_assign = time.time()
    # data = {}
    # data['weights'] = np.transpose(x_0).tolist()[0]
    # data['values'] = [1]*len(data['weights'])

    # assert len(data['weights']) == len(data['values'])
    # data['num_items'] = len(data['weights'])
    # data['all_items'] = range(data['num_items'])

    
    # data['bin_capacities'] = [capacity[host]*server_node.z_storage[cur_iter-1][host] for host in server_node.client_hostname_list]
    
    # data['num_bins'] = len(data['bin_capacities'])
    # data['all_bins'] = range(data['num_bins'])

    # print("Job weights: ", data['weights'])
    # print("Node capacity: ", data['bin_capacities'])

    # # Create the mip solver with the SCIP backend.
    # solver = pywraplp.Solver.CreateSolver('SCIP')
    # if solver is None:
    #     print('SCIP solver unavailable.')
    #     return

    # # Variables.
    # # x[i, b] = 1 if item i is packed in bin b.
    # x = {}
    # for i in data['all_items']:
    #     for b in data['all_bins']:
    #         x[i, b] = solver.BoolVar(f'x_{i}_{b}')

    # # Constraints.
    # # Each item is assigned to at most one bin.
    # for i in data['all_items']:
    #     solver.Add(sum(x[i, b] for b in data['all_bins']) <= 1)

    # # The amount packed in each bin cannot exceed its capacity.
    # for b in data['all_bins']:
    #     solver.Add(
    #         sum(x[i, b] * data['weights'][i]
    #             for i in data['all_items']) <= data['bin_capacities'][b])

    # # Objective.
    # # Maximize total value of packed items.
    # objective = solver.Objective()
    # for i in data['all_items']:
    #     for b in data['all_bins']:
    #         objective.SetCoefficient(x[i, b], data['values'][i])
    # objective.SetMaximization()

    # status = solver.Solve()

    # assignment = {}
    # if status == pywraplp.Solver.OPTIMAL:
    #     print(f'Total job assigned: {objective.Value()}')
    #     total_weight = 0
    #     for b in data['all_bins']:
    #         print('Node: ',server_node.client_hostname_list[b])
    #         bin_weight = 0
    #         bin_value = 0
    #         for i in data['all_items']:
    #             if x[i, b].solution_value() > 0:
    #                 print(
    #                     f"Assigned Job {i} weight: {data['weights'][i]}"
    #                 )
    #                 bin_weight += data['weights'][i]
    #                 bin_value += data['values'][i]
    #                 assignment[i] = server_node.client_hostname_list[b]
    #         # print(f'Packed Job CPU cycles: {bin_weight}')
    #         # print(f'Packed number of Jobs: {bin_value}\n')
    #         total_weight += bin_weight
            
    #     print(f'Total packed CPU cycles: {total_weight}')
    # else:
    #     print('The problem does not have an optimal solution.')

    # print("---End Job Assigning---")
    # print("Job Scheduling takes %s seconds" % (time.time() - start_job_assign))
    # ###############################################
    
    
    
    # print(is_complete)

    # cpu_to_machine = {}
    # for i,n in enumerate(server_node.client_hostname_list):
    #     if i < 12:
    #         cpu_to_machine[n] = 'caelum-201'
    #     elif i < 18:
    #         cpu_to_machine[n] = 'caelum-601'
    #     elif i < 24:
    #         cpu_to_machine[n] = 'caelum-602'
    #     elif i < 30:
    #         cpu_to_machine[n] = 'caelum-603'
    # ###############################################
    # #Start Job assinging
    # print("Scheduled Jobs: ", list(assignment.keys()))
    # for id in list(assignment.keys()):
    #     print(id)
    #     # subprocess.check_output(['export','JOBID=','job'+str(id)],shell=True)
    #     # subprocess.check_output(["export","NUMCPU=","1"],shell=True)
    #     # subprocess.check_output(["export","NODE=",cpu_to_machine[id]],shell=True)
    #     # subprocess.check_output(["envsubst","<","../job-pod.yaml","|","kubectl","apply", "-f","-"],shell=True)
    #     jobstr = "job"+str(id)
    #     with open('../jobs/job-pod.yaml', 'r') as file :
    #         job_tmpl = file.read()
    #     filedata = job_tmpl.replace('$JOBID',jobstr).replace("$NUM_CPU","1").replace("$NODE",cpu_to_machine[assignment[id]])
        # filename = "../jobs/"+jobstr+".yaml"
    #     with open(filename, 'w') as file:
    #       file.write(filedata)
    #     subprocess.check_output(["kubectl","apply", "-f", filename])


if __name__ == "__main__":
    #---------- Record Consensus Status ----------
    random.seed(1234)
    # seeds = random.sample(range(1, 100), 10)
    seeds = [57, 15, 1, 12, 75, 5, 86, 89, 11, 13]
    # seeds = [15]
    # nodes = [30,40,50,60,70,80,90,100]
    nodes = [50,60,70]
    #---------- Start Server Node ----------
    HOSTNAME = urllib.request.urlopen(URL_REQUEST).read().decode('utf8')
    server_node = MyOwnPeer2PeerNode(HOSTNAME, DEFAULT_PORT, HOSTNAME)
    server_node.start()
    # TODO: check if sleep is necessary here
    time.sleep(10)
    #---------- Start Running Trials ----------
    for num_clients in nodes:
        print("Number of clients: ", num_clients)
        # Create and run client deployment files
        tmplstr = "client-deployment-"+str(num_clients)
        with open('../deployments/client/client-deployment.yaml', 'r') as file :
            client_tmpl = file.read()
        filedata = client_tmpl.replace('$NUM_NODES',str(num_clients))
        filename = "../deployments/client/"+tmplstr+".yaml"
        with open(filename, 'w') as file:
            file.write(filedata)
        subprocess.check_output(["kubectl","apply", "-f", filename])
        # Trials
        for i in range(len(seeds)):
            random.seed(seeds[i])
            np.random.seed(seeds[i])
            print("Iteration: ", i)
            flag, consensus_time, iteration, diameter = start_server(num_clients,server_node)
            if flag == 1:
                content = str(num_clients) +  " " + str(i) + " " + str(consensus_time) + " " + str(iteration) + " " + str(diameter) + "\n"
                print("Results: ",content)

                myfile = open('../log.txt', 'a')
                myfile.write(content)
                
                # Number of client logs received
                while len(server_node.msg_ex_net_out_list) < 10:
                    # print(len(server_node.msg_ex_net_out_list))
                    # print(server_node.msg_ex_net_out_list)
                    # print("Wait for all clients sending back results..")
                    time.sleep(5)
                
                myfile.write(json.dumps(server_node.local_comp_time_list)+ '\n')
                myfile.write(json.dumps(server_node.msg_ex_xy_time_list)+ '\n')
                myfile.write(json.dumps(server_node.msg_ex_z_time_list)+ '\n')
                myfile.write(json.dumps(server_node.local_comp_cpu_list)+ '\n')
                myfile.write(json.dumps(server_node.local_comp_mem_list)+ '\n')
                myfile.write(json.dumps(server_node.local_comp_disk_list)+ '\n')
                myfile.write(json.dumps(server_node.local_comp_net_in_list)+ '\n')
                myfile.write(json.dumps(server_node.local_comp_net_out_list)+ '\n')
                myfile.write(json.dumps(server_node.msg_ex_cpu_list)+ '\n')
                myfile.write(json.dumps(server_node.msg_ex_mem_list)+ '\n')
                myfile.write(json.dumps(server_node.msg_ex_disk_list)+ '\n')
                myfile.write(json.dumps(server_node.msg_ex_net_in_list)+ '\n')
                myfile.write(json.dumps(server_node.msg_ex_net_out_list)+ '\n')

                print("Server Finish logging")

                myfile.close()

            server_node.reset()
            # TODO: check if sleep is necessary here
            time.sleep(20)
    