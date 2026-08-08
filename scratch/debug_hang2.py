import sys
import os
sys.path.insert(0, os.path.abspath("src"))
sys.path.insert(0, os.path.abspath("."))
from kaggle_environments import make
from benchmark_scheduler import run_simulation
from fieldops.managers.worker_manager import HybridWorkerManager
from fieldops.agent import _coordinator_instance

class DebugHybrid(HybridWorkerManager):
    def execute(self, state, context):
        print(f"Day {state.day} units: {1 + len(state.my_farm.hands)}")
        acts = super().execute(state, context)
        print(f"Returned: {acts}")
        return acts

_coordinator_instance.managers[2] = DebugHybrid()

print("Starting 2-worker simulation on seed 100")
run_simulation((100, 2))
print("Done")
