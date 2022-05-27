import csv
import numpy as np
import random

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
                task_cpu.append(cpu)
                cpu_sum += cpu
print(cpu_sum)
# print(len(task_cpu))
# print(task_cpu)
len = 9

workload = []
r = [random.random() for i in range(1,len+1)]
s = sum(r)
r = [ i/s for i in r ]

for p in r:
    workload.append(cpu_sum * p)

print(workload)
print(sum(workload))