import sys
import os
sys.path.insert(0, os.path.abspath("src"))
sys.path.insert(0, os.path.abspath("."))
from benchmark_scheduler import run_simulation
print("Running...")
try:
    res = run_simulation((100, 2))
    print(res["metrics"]["reward"])
except Exception as e:
    import traceback
    traceback.print_exc()
print("Done")
