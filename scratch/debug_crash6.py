import sys
import os
sys.path.insert(0, os.path.abspath("src"))
sys.path.insert(0, os.path.abspath("."))
from benchmark_scheduler import run_simulation
from kaggle_environments import make

print("Running...")
res = run_simulation((100, 12))
print("Done")
