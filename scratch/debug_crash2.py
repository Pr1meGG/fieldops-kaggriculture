import sys
import os
sys.path.insert(0, os.path.abspath("src"))
sys.path.insert(0, os.path.abspath("."))
from benchmark_scheduler import run_simulation
from kaggle_environments import make

print("Running...")
env = make("kaggriculture", debug=True, configuration={"episodeSteps": 721, "seed": 100})
try:
    res = run_simulation((100, 16))
    print(res["metrics"]["reward"])
except Exception as e:
    import traceback
    traceback.print_exc()
print("Done")
