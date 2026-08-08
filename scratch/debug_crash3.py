import sys
import os
sys.path.insert(0, os.path.abspath("src"))
sys.path.insert(0, os.path.abspath("."))
from benchmark_scheduler import run_simulation
from kaggle_environments import make

import benchmark_scheduler
original_wrapper = benchmark_scheduler.wrapper

def new_wrapper(obs, cfg=None):
    res = original_wrapper(obs, cfg)
    print("STEP", obs["step"], "ACTIONS:", res)
    return res

benchmark_scheduler.wrapper = new_wrapper

print("Running...")
try:
    res = run_simulation((100, 16))
    print(res["metrics"]["reward"])
except Exception as e:
    import traceback
    traceback.print_exc()
print("Done")
