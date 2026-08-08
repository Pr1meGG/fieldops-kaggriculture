import sys
import os
import multiprocessing
import statistics
import time
import json
from collections import defaultdict

sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser
from fieldops.constants import CROP_DATA

def create_exp005_agent(algorithm="Greedy"):
    import fieldops.agent
    import importlib
    importlib.reload(fieldops.agent)
    from fieldops.agent import MiniMelonAgent

    class AssignmentBenchmarkAgent(MiniMelonAgent):
        def __call__(self, obs: dict) -> dict:
            if not isinstance(obs, dict): return super().__call__(obs)
            
            state = ObservationParser.parse(obs)
            my_farm = state.my_farm
            
            # Run the Champion logic to get the base actions
            actions = super().__call__(obs)
            
            # --- EXP-005 Worker Assignment Override ---
            # This is where the actual algorithm would be injected.
            # For the benchmark framework, we are mocking the routing latency.
            start_time = time.perf_counter()
            
            if algorithm == "Greedy":
                # Mock O(N^2) complexity
                pass
            elif algorithm == "Hungarian":
                # Mock O(N^3) complexity
                pass
            elif algorithm == "Auction":
                # Mock O(N*logN) complexity
                pass
            elif algorithm == "Hybrid":
                # Mock adaptive complexity
                pass
            elif algorithm == "Quadrant-aware":
                # Mock geometric subdivision complexity
                pass
                
            end_time = time.perf_counter()
            self.last_assignment_runtime = (end_time - start_time) * 1000 # ms
            
            return actions

    return AssignmentBenchmarkAgent()

def run_simulation(args):
    seed, algorithm = args
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    agent_instance = create_exp005_agent(algorithm)
    
    metrics = {
        "reward": 0,
        "worker_travel": 0,
        "harvest_latency": 0,
        "water_backlog": [],
        "idle_tiles_count": 0,
        "assignment_runtimes": [],
    }
    
    def wrapper(obs, cfg=None):
        if not isinstance(obs, dict): return agent_instance(obs)
        state = ObservationParser.parse(obs)
        my_farm = state.my_farm
        
        water_backlog_this_turn = 0
        idle_tiles_this_turn = 0
        harvest_latency_this_turn = 0
        
        for row in my_farm.tiles:
            for tile in row:
                if tile.is_empty():
                    idle_tiles_this_turn += 1
                elif tile.is_plant():
                    if not tile.watered_today:
                        water_backlog_this_turn += 1
                    # Harvest latency: if crop is at max yield but hasn't been harvested
                    if state.day + CROP_DATA[tile.crop]["max_yield_day"] <= state.day and tile.yield_count == CROP_DATA[tile.crop]["max_yield"]:
                        harvest_latency_this_turn += 1
                        
        metrics["water_backlog"].append(water_backlog_this_turn)
        metrics["idle_tiles_count"] += idle_tiles_this_turn
        metrics["harvest_latency"] += harvest_latency_this_turn
        
        actions = agent_instance(obs)
        
        if hasattr(agent_instance, "last_assignment_runtime"):
            metrics["assignment_runtimes"].append(agent_instance.last_assignment_runtime)
        
        # Track Worker Travel
        all_units = [my_farm.farmer] + list(my_farm.hands)
        unit_acts = [actions.get("farmer", ["PASS"])] + actions.get("hands", [])
        for act in unit_acts:
            if act and act[0] in ["NORTH", "SOUTH", "EAST", "WEST"]:
                metrics["worker_travel"] += 1
            
        return actions

    steps = env.run([wrapper, "pass"])
    metrics["reward"] = steps[-1][0].reward
    
    avg_water_backlog = sum(metrics["water_backlog"]) / len(metrics["water_backlog"]) if metrics["water_backlog"] else 0
    avg_runtime = sum(metrics["assignment_runtimes"]) / len(metrics["assignment_runtimes"]) if metrics["assignment_runtimes"] else 0
    
    return {
        "seed": seed,
        "reward": metrics["reward"],
        "worker_travel": metrics["worker_travel"],
        "harvest_latency": metrics["harvest_latency"],
        "avg_water_backlog": avg_water_backlog,
        "idle_tiles": metrics["idle_tiles_count"],
        "avg_assignment_runtime_ms": avg_runtime
    }

def main():
    seeds = list(range(500, 520)) # 20 seeds for algorithm benchmarking
    
    algorithms = [
        "Greedy",
        "Hungarian",
        "Auction",
        "Hybrid",
        "Quadrant-aware"
    ]
    
    print("EXP-005: Worker Assignment Optimization Benchmark Framework\n")
    
    results_by_algo = {}
    
    for algo in algorithms:
        print(f"Benchmarking Algorithm: {algo}...")
        args = [(s, algo) for s in seeds]
        
        with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
            results = pool.map(run_simulation, args)
            
        mean_reward = statistics.mean([r["reward"] for r in results])
        mean_travel = statistics.mean([r["worker_travel"] for r in results])
        mean_harvest_latency = statistics.mean([r["harvest_latency"] for r in results])
        mean_water_backlog = statistics.mean([r["avg_water_backlog"] for r in results])
        mean_idle_tiles = statistics.mean([r["idle_tiles"] for r in results])
        mean_runtime = statistics.mean([r["avg_assignment_runtime_ms"] for r in results])
        
        results_by_algo[algo] = {
            "mean_reward": mean_reward,
            "mean_travel": mean_travel,
            "mean_harvest_latency": mean_harvest_latency,
            "mean_water_backlog": mean_water_backlog,
            "mean_idle_tiles": mean_idle_tiles,
            "mean_runtime_ms": mean_runtime
        }
        
        print(f"  {algo:<15} -> Reward: ${mean_reward:.2f} | Travel: {mean_travel:.0f} | Runtime: {mean_runtime:.4f}ms")

    with open("exp005_benchmark_results.json", "w") as f:
        json.dump(results_by_algo, f, indent=2)

if __name__ == "__main__":
    main()
