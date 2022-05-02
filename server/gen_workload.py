import numpy as np

def gen_workload(min_w:int, max_w:int, len:int, job_scheduling:bool):
    # {'192.168.200.78': 5000, '192.168.82.190': 11000, '192.168.193.97': 11000, '192.168.65.162': 11000, '192.168.112.40': 11000, '192.168.171.114': 5000, '192.168.98.17': 5000, '192.168.110.43': 5000, '192.168.9.14': 5000}
    if job_scheduling:
        # 1 task need 100 
        workload = np.random.randint(1,10, size=[len,1])*100
    else:
        workload = np.random.randint(min_w,max_w+1, size=[len,1])
    return workload