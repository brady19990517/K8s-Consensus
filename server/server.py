from ast import JoinedStr
from http import server
import sys
import time
import argparse
import subprocess
from docker import Client
import os
import numpy as np
import random
import copy
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
import re

from MyOwnPeer2PeerNode import MyOwnPeer2PeerNode

DOCKER_SOCKET_URL = 'unix://var/run/docker.sock'
URL_REQUEST = 'https://v4.ident.me'
DEFAULT_PORT = 10001


def start_server(num_clients, server_node, HOSTNAME, x_0,job_scheduling=False,max_iter=1000,epsilon=1e-5,use_variable_capacities = 0):
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
    # # Generate Workload
    # x_0 = gen_workload(workload_min, workload_max, num_clients)
    # print("x_0:", np.transpose(x_0)[0])
    # Generate Capacity
    y_0=None
    if job_scheduling == True:
        pass
    else:
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
    capacity = None
    if job_scheduling:
        capacity, ip_node_dict = get_capacity()
        print(capacity)
        
    else:
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
    print("[Consensus] Consensus takes %s seconds" % (consensus_time))
    print("[Consensus] Ending at iteration: ", cur_iter)
    print("[Consensus] All ratio ended at: ", json.dumps(server_node.z_storage[cur_iter]))
    print("[Consensus] End Consensus")
    # Close client node
    server_node.send_to_nodes(str({"stop":0}))
    # TODO: check if sleep is necessary here
    time.sleep(5)
    # server_node.stop()
    # is_complete = subprocess.check_output(["kubectl","delete", "deployments/client"])
    optimal_cap = {}
    for host in server_node.client_hostname_list:
        optimal_cap[host] = capacity[host]*server_node.z_storage[cur_iter][host]


    return 1, consensus_time, cur_iter, diameter, optimal_cap, ip_node_dict, capacity

def get_capacity():
    lines = subprocess.check_output(["kubectl","describe","nodes"]).decode("utf-8").split('\n')
    name_index = []
    cpu_index = []
    total_cpu_index = []
    for i,l in enumerate(lines):
        if 'Name:' in l and 'caelum-' in l:
            name_index.append(i)
        if 'Allocatable' in l:
            total_cpu_index.append(i+1)
        if 'Allocated resources' in l:
            cpu_index.append(i+4)
    # Get node total capacity and current capacity to obtain remain capcity
    result = {}
    for i,idx in enumerate(cpu_index):
        name_arr = lines[name_index[i]].split()
        total_cpu_arr = lines[total_cpu_index[i]].split()
        cpu_arr = lines[idx].split()
        name = name_arr[1]
        total_cap = int(total_cpu_arr[1])*1000
        cap = cpu_arr[1]
        if 'm' in cap:
            cap = int(cap[:-1])
        else:
            cap = int(cap)*1000
        result[name] = total_cap - cap
    # Match each scheduler to a node
    lines = subprocess.check_output(["kubectl","get","pod","-o=custom-columns=NODE:.spec.nodeName,IP:.status.podIP,NAME:metadata.name"]).decode("utf-8").split('\n')
    node_ip_dict = {}
    for i,l in enumerate(lines):
        if i==0 or len(l)==0:
            continue
        arr = lines[i].split()
        if 'client' not in arr[2]:
            continue
        print(arr)
        node_ip_dict[arr[0]] = arr[1]
    ip_node_dict = {v: k for k, v in node_ip_dict.items()}
    print(node_ip_dict)
    new_result = {}
    for key, value in result.items():
        if key == 'caelum-102':
            continue
        new_result[node_ip_dict[key]] = value
    return new_result, ip_node_dict
        
def job_scheduler_mk(workload, capacity, full_cap):
    ################Job/Task Distribute#################
    print("---Start Job Assigning---")
    start_job_assign_time = time.time()
    data = {}
    node_list = list(capacity.keys())
    data['workload'] = np.transpose(workload).tolist()[0]
    #Assume each task need 0.001 cpu
    data['task_per_job'] = copy.deepcopy(data['workload'])
    #Assume each job has only 1 task
    # data['task_per_job'] = [1]*len(data['workload'])
    assert len(data['workload']) == len(data['task_per_job'])
    data['num_jobs'] = len(data['workload'])
    data['all_jobs'] = range(data['num_jobs'])
    data['node_capacities'] = list(capacity.values())
    data['num_nodes'] = len(data['node_capacities'])
    data['all_nodes'] = range(data['num_nodes'])

    print("Job size: ", data['workload'])
    print("List of nodes: ", list(capacity.keys()))
    print("Passed in cpapcity: ", capacity)
    print("Node capacity: ", data['node_capacities'])

    # Create the mip solver with the SCIP backend.
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if solver is None:
        print('SCIP solver unavailable.')
        return

    # Variables.
    # x[i, b] = 1 if job i is assigned to node b.
    x = {}
    for i in data['all_jobs']:
        for b in data['all_nodes']:
            x[i, b] = solver.BoolVar(f'x_{i}_{b}')

    # Constraints.
    # Each item is assigned to at most one bin.
    for i in data['all_jobs']:
        solver.Add(sum(x[i, b] for b in data['all_nodes']) <= 1)

    # The amount packed in each bin cannot exceed its capacity.
    for b in data['all_nodes']:
        solver.Add(
            sum(x[i, b] * data['workload'][i]
                for i in data['all_jobs']) <= data['node_capacities'][b])

    # Objective.
    # Maximize total value of packed items.
    objective = solver.Objective()
    for i in data['all_jobs']:
        for b in data['all_nodes']:
            objective.SetCoefficient(x[i, b], data['task_per_job'][i])
    objective.SetMaximization()

    status = solver.Solve()

    assignment = {}
    if status == pywraplp.Solver.OPTIMAL:
        print(f'Total job/task assigned (Assume 1 task per job): {objective.Value()}')
        total_workload = 0
        for b in data['all_nodes']:
            print('Node: ',node_list[b])
            node_workload_assigned = 0
            node_job_assigned = 0
            for i in data['all_jobs']:
                if x[i, b].solution_value() > 0:
                    print(
                        f"Assigned Job {i} workload: {data['workload'][i]}"
                    )
                    node_workload_assigned += data['workload'][i]
                    node_job_assigned += data['task_per_job'][i]
                    assignment[i] = node_list[b]
            # print(f'Packed Job CPU cycles: {bin_weight}')
            # print(f'Packed number of Jobs: {bin_value}\n')
            total_workload += node_workload_assigned
            
        print(f'Total packed CPU cycles: {total_workload}')
    else:
        print('The problem does not have an optimal solution.')

    print("---End Job Assigning---")
    print("Job Scheduling takes %s seconds" % (time.time() - start_job_assign_time))
    for i in data['all_jobs']:
        if i not in assignment:
            assignment[i] = None
    return assignment
    ###############################################

def job_scheduler_greedy(workload, capacity, full_cap):
    assignment = {}
    for c in capacity.keys():
        assignment[c] = []
    #order of client
    workload = np.transpose(workload)[0]
    cap_order = [k for k, v in sorted(capacity.items(), key=lambda item: item[1], reverse=True)]

    #order of job
    job_order = np.argsort(workload)[::-1]

    remain_cap = copy.deepcopy(full_cap)

    total_tasks = np.sum(workload)/10

    
    print("total_tasks: ", total_tasks)

    job_idx = 0
    task_idx = 0
    assigned_tasks = 0
    for c in cap_order:
        cap = capacity[c]
        while cap > 0:
            cap -= 10
            if cap < 0:
                break
            else:
                remain_cap[c] -= 10
                print("Assiging Job ",job_order[job_idx],"Task ",task_idx,"to Client ",c,"Capcaity ",cap,"/",capacity[c])
                assignment[c].append((job_order[job_idx], task_idx))
                if task_idx==(workload[job_order[job_idx]]/10)-1:
                    task_idx = 0
                    job_idx+=1
                else:
                    task_idx+=1
                assigned_tasks+=1
                if assigned_tasks == total_tasks:
                    print("All tasks assigned")
                    break
        if assigned_tasks == total_tasks:
            print("All tasks assigned")
            break
    
    if assigned_tasks == total_tasks:
        print("All tasks assigned")
        return assignment
    print("Extra space needed... Schedule to top capacity node again")
    #Not all task are assinged because each client remaining space are unused
    #Assgin remaining task to top clients
    for c in cap_order:
        cap = remain_cap[c]
        while cap > 0:
            cap -= 10
            if cap < 0:
                break
            else:
                remain_cap[c] -= 10
                print("Assiging Job ",job_order[job_idx],"Task ",task_idx,"to Client ",c,"Remaining capcaity ",remain_cap[c],"/",full_cap[c])
                assignment[c].append((job_order[job_idx], task_idx))
                if task_idx==(workload[job_order[job_idx]]/10)-1:
                    task_idx = 0
                    job_idx+=1
                else:
                    task_idx+=1
                assigned_tasks+=1
                if assigned_tasks == total_tasks:
                    print("All tasks assigned")
                    break
        if assigned_tasks == total_tasks:
            print("All tasks assigned")
            break
    return assignment

def job_scheduler(workload, capacity, full_cap, type):
    start_job_schedule_time = time.time()
    if type == 'mk':
        assignment = job_scheduler_mk(workload, capacity, full_cap)
    elif type == 'greedy':
        assignment = job_scheduler_greedy(workload, capacity, full_cap)
    job_schedule_time = time.time() - start_job_schedule_time
    return assignment, job_schedule_time
    
def run_jobs(assignment,x_0,ip_node_dict,completed_jobs):
    #Start Job assinging
    workload = np.transpose(x_0).tolist()[0]
    print("Start running jobs: ", list(assignment.keys()))
    created_jobs = []
    for id in list(assignment.keys()):
        if assignment[id] is None:
            continue
        print(id)
        req_cpu = str(workload[id]) + 'm'
        jobstr = "job-pod-"+str(id)
        created_jobs.append(jobstr)
        with open('../deployments/job/job-pod.yaml', 'r') as file:
            job_tmpl = file.read()
        filedata = job_tmpl.replace('$JOBID',jobstr).replace("$NUM_CPU",req_cpu).replace("$NODE",ip_node_dict[assignment[id]]).replace("$SLEEP_TIME",str(random.randint(15, 180)))
        filename = "../deployments/job/"+jobstr+".yaml"
        with open(filename, 'w') as file:
            file.write(filedata)
        subprocess.check_output(["kubectl","apply", "-f", filename])

    # Rerun consensus algorithm if two jobs completed
    prev_completed_jobs = completed_jobs
    completed_jobs = 0
    # Stop looping when at least one job complete
    while prev_completed_jobs >= completed_jobs:
        out = subprocess.check_output(["kubectl","get", "jobs", "--field-selector", "status.successful=1"])
        print(out)
        completed_jobs = out.count(b'\n')-1
        time.sleep(3)
        
    print("At least one job completed")

    return completed_jobs

        # kubectl wait --for=condition=complete --timeout=30s job/myjob

def run_tasks(assignment,ip_node_dict):
    start_execute_time = time.time()
    node_task_dict = {}
    for ip in list(assignment.keys()):
        client = ip_node_dict[ip]
        print("Executing tasks on node: ", client)
        num_task = len(assignment[ip])
        node_task_dict[client] = num_task
        if num_task == 0:
            continue
        jobstr = "job-pod-"+client
        with open('../deployments/job/job-pod.yaml', 'r') as file:
            job_tmpl = file.read()
        filedata = job_tmpl.replace('$NODE',client).replace("$NUM_TASKS",str(num_task)).replace("$NODE",client)
        filename = "../deployments/job/"+jobstr+".yaml"
        with open(filename, 'w') as file:
            file.write(filedata)
        subprocess.check_output(["kubectl","apply", "-f", filename])
    
    
    while True:
        complete = 0
        for key, task in node_task_dict.items():
            lines = subprocess.check_output(["kubectl","get", "jobs", key])
            line_arr = lines.split(b'\n')[1]
            arr = line_arr.split()
            finish_task = arr[1].split(b'/')[0]
            finish_task = int(finish_task)
            if finish_task == task:
                complete+=1
        if complete == len(assignment):
            break
    print("All task finish exec")
    execute_time = time.time() - start_execute_time
    return execute_time

def default_scheduler_run_tasks(x_0):
    workload = np.transpose(x_0)[0]
    task_arr = []
    for job in workload:
        task_arr.append(job/10)
    start_execute_time = time.time()
    node_task_dict = {}
    for i,tasks in enumerate(task_arr):
        jobstr = "default-scheduler-job-" + str(i)
        node_task_dict[jobstr] = tasks
        with open('../deployments/job/default-scheduler-job.yaml', 'r') as file:
            job_tmpl = file.read()
        filedata = job_tmpl.replace("$NUM_TASKS",str(tasks)).replace('$JOB_NAME',jobstr)
        filename = "../deployments/job/"+jobstr+".yaml"
        with open(filename, 'w') as file:
            file.write(filedata)
        subprocess.check_output(["kubectl","apply", "-f", filename])
    
    
    while True:
        complete = 0
        for key, task in node_task_dict.items():
            lines = subprocess.check_output(["kubectl","get", "jobs", key])
            line_arr = lines.split(b'\n')[1]
            arr = line_arr.split()
            finish_task = arr[1].split(b'/')[0]
            finish_task = int(finish_task)
            if finish_task == task:
                complete+=1
        if complete == len(workload):
            break
    print("All task finish exec")
    execute_time = time.time() - start_execute_time
    return execute_time
    

def node_init():
    #---------- Start Server Node ----------
    HOSTNAME = urllib.request.urlopen(URL_REQUEST).read().decode('utf8')
    server_node = MyOwnPeer2PeerNode(HOSTNAME, DEFAULT_PORT, HOSTNAME)
    server_node.start()
    time.sleep(10)
    return server_node, HOSTNAME

def create_clients(num_clients):
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

def log(server_node, num_clients, i, consensus_time, iteration, diameter):
    content = str(num_clients) +  " " + str(i) + " " + str(consensus_time) + " " + str(iteration) + " " + str(diameter) + "\n"
    print("Results: ",content)

    myfile = open('../log.txt', 'a')
    myfile.write(content)
    
    # Number of client logs received
    NUMBER_OF_LOGS = 9
    while len(server_node.msg_ex_net_out_list) < NUMBER_OF_LOGS:
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
    myfile.close()

def run_consensus(server_node,HOSTNAME,nodes,trials,job_scheduling=False,x_0=None):
    for num_clients in nodes:
        create_clients(num_clients)
        # Trials
        for i in range(trials):
            print("Iteration: ", i)
            # Generate Workload
            if job_scheduling:
                assert(x_0 is not None)
            else:
                x_0 = gen_workload(100, 1000, num_clients, job_scheduling)
            print('workload: ', np.transpose(x_0)[0])
            flag, consensus_time, iteration, diameter, capacity, ip_node_dict, full_cap = start_server(num_clients,server_node,HOSTNAME,x_0,job_scheduling)
            if flag == 1:
                log(server_node, num_clients, i, consensus_time, iteration, diameter)
            print("Server Finish logging")
            while server_node.client_reset_num < num_clients:
                time.sleep(2)
            print("[Server] all client reset")
            if job_scheduling == True:
                print("[Server] reset server: ", server_node.reset())
                print("[Server] preparing to do job scheduling")
                # Each task need 0.001 cpu
                # All task of the same job should be put on one node (Multiple_Knapsack) mk
                # Tasks of a node can be put on different nodes (Greedy) greedy
                #TODO: Currently assuming one task per job
                assignment,job_schedule_time = job_scheduler(x_0,capacity,full_cap,type='greedy')
                execute_time = run_tasks(assignment,ip_node_dict)
                print("Consensus Time: ", consensus_time, "Job Scheduling Time: ", job_schedule_time, "Job Execution Time: ", execute_time)
                total_time = consensus_time + job_schedule_time + execute_time
                print('Total Time: ', total_time)


                #--------- We now assume that all jobs/ tasks are scheduled in a single round---------
                # completed_jobs = run_jobs(assignment,x_0,ip_node_dict,0)
                # print(assignment)

                # for job_id in assignment.keys():
                #     if assignment[job_id] != None:
                #         x_0[job_id] = 0
                

                # print('Schedule unscheduled jobs: ', x_0)
                # -------------- Second Round --------------
                # flag, consensus_time, iteration, diameter, capacity, ip_node_dict = start_server(num_clients,server_node,HOSTNAME,x_0,job_scheduling)
                # if flag == 1:
                #     log(server_node, num_clients, i, consensus_time, iteration, diameter)
                # print("Server Finish logging")
                # while server_node.client_reset_num < num_clients:
                #     time.sleep(2)
                # print("[Server] all client reset")
                # if job_scheduling == True:
                #     print("[Server] reset server: ", server_node.reset())
                #     print("[Server] preparing to do job scheduling")
                #     # Each task need 0.001 cpu
                #     # All task of the same job should be put on one node (Multiple_Knapsack) mk
                #     # Tasks of a node can be put on different nodes (Greedy) greedy
                #     #TODO: Currently assuming one task per job
                #     assignment = job_scheduler(x_0,capacity,type='mk')
                #     completed_jobs = run_jobs(assignment,x_0,ip_node_dict,completed_jobs)
                #     print(assignment)

                #     for job_id in assignment.keys():
                #         if assignment[job_id] != None:
                #             x_0[job_id] = 0
                #     print('Schedule unscheduled jobs second round: ', x_0)
                #--------------------------------------------------------------------------
                
            server_node.reset()

if __name__ == "__main__":
    server_node, HOSTNAME = node_init()
    #---------- Setting Parameters ----------
    random.seed(1234)
    # trials = 10
    trials = 1
    # nodes = [20,30,40,50,60,70,80,90,100]
    nodes = [9]
    job_scheduling = True
    
    #---------- Start Running Trials ----------
    if job_scheduling:
        assert(len(nodes)==1 and nodes[0]==9)
        assert(trials == 1)
    x_0 = gen_workload(100, 1000, 9, job_scheduling)
    # run_consensus(server_node,HOSTNAME,nodes,trials,job_scheduling,x_0)
    base_time = default_scheduler_run_tasks(x_0)
    print("Base Time: ", base_time)


        


            
    