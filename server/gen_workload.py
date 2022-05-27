import numpy as np
import csv
import random

def gen_workload(min_w:int, max_w:int, len:int, job_scheduling:bool, real_workload:bool):
    # {'192.168.200.78': 5000, '192.168.82.190': 11000, '192.168.193.97': 11000, '192.168.65.162': 11000, '192.168.112.40': 11000, '192.168.171.114': 5000, '192.168.98.17': 5000, '192.168.110.43': 5000, '192.168.9.14': 5000}
    if real_workload:
        task_cpu = []
        cpu_sum = 0
        with open('google-cluster.csv', newline='') as csvfile:
            spamreader = csv.reader(csvfile, delimiter=',', quotechar='|')
            for row in spamreader:
                cpu = float(row[2])
                if cpu <= 0.001:
                    continue
                else:
                    if np.random.uniform(low=0, high=1) < 0.001:
                        task_cpu.append(cpu*1000)
                        cpu_sum += cpu
        workload = []
        r = [random.random() for i in range(1,len+1)]
        s = sum(r)
        r = [ i/s for i in r ]

        for p in r:
            workload.append((cpu_sum * p)*1000)

        print(workload)
        print(np.resize(workload, (len(workload),1)))
        return np.resize(workload, (len(workload),1)), task_cpu
    else:
        if job_scheduling:
            # 1 task need 100 
            workload = np.random.randint(1,10, size=[len,1])*100
        else:
            workload = np.random.randint(min_w,max_w+1, size=[len,1])
        total_task = 0
        for w in np.transpose(workload)[0]:
            total_task += w / 100
        return workload, [100]*int(total_task)