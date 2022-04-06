from functools import total_ordering
import numpy as np

def load_workload(file, nodes:int):
    jobid = 0
    total_time = 0
    workload_arr = []
    # Process workload file
    f = open('YH.tr', 'r')
    for row in f:
        temp = []
        row = row.split()
        num_tasks = int(row[1])
        est_time = float(row[2])
        actual_duration = []
        for index in range(num_tasks):
            actual_duration.append(float(row[3+index]))
            total_time += float(row[3+index])
        # Replace the template file with actual values
        temp.extend([jobid,num_tasks,est_time,actual_duration])
        jobid += 1
        workload_arr.append(temp)
        if jobid == nodes:
            break
    
    return workload_arr, total_time