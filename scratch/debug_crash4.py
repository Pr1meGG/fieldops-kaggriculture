import sys
import os
sys.path.insert(0, os.path.abspath("src"))
sys.path.insert(0, os.path.abspath("."))
from benchmark_scheduler import run_simulation
from kaggle_environments import make

import benchmark_scheduler

def safe_run():
    print("Running...")
    try:
        res = run_simulation((100, 12))
        print(res["metrics"]["reward"])
    except Exception as e:
        import traceback
        traceback.print_exc()
    print("Done")

safe_run()
