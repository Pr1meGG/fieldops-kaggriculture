import sys
import os
sys.path.insert(0, os.path.abspath("src"))
sys.path.insert(0, os.path.abspath("."))
from benchmark_scheduler import run_simulation
from kaggle_environments import make
import benchmark_scheduler

original_wrapper = benchmark_scheduler.wrapper
def new_wrapper(*args, **kwargs):
    try:
        return original_wrapper(*args, **kwargs)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e

benchmark_scheduler.wrapper = new_wrapper

print("Running...")
res = run_simulation((100, 12))
print("Done")
