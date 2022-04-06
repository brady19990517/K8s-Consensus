import numpy as np

def gen_workload(min_w:int, max_w:int, len:int):
    workload = np.random.randint(min_w,max_w+1, size=[len,1])
    return workload