import sys
import os
import multiprocessing
import statistics
import json
import importlib

sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser
from fieldops.constants import CROP_DATA

def create_sweep_agent(tiles_per_worker=12):
    """
    Creates a modified version of the Champion agent by dynamically patching the hiring logic
    for the parameter sweep, without touching the original agent.py file on disk.
    """
    import fieldops.agent
    importlib.reload(fieldops.agent)
    from fieldops.agent import MiniMelonAgent

    class SweepAgent(MiniMelonAgent):
        def __call__(self, obs: dict) -> dict:
            if not isinstance(obs, dict): return super().__call__(obs)
            
            # Intercept state to override hiring logic
            state = ObservationParser.parse(obs)
            my_farm = state.my_farm
            
            actions = super().__call__(obs)
            
            # Re-apply our swept hiring logic
            # Remove any existing HIRE actions from the base agent
            actions["market"] = [a for a in actions["market"] if a[0] != "HIRE"]
            
            quads_unlocked = len(my_farm.unlocked_quadrants)
            total_tiles = quads_unlocked * 25
            
            # total workers we want = total_tiles // tiles_per_worker
            # hands we want = total_workers - 1 (the farmer)
            target_hands = (total_tiles // tiles_per_worker) - 1
            target_hands = max(0, target_hands) # can't be negative
            
            if my_farm.hires_today < target_hands and my_farm.money >= 50:
                actions["market"].append(["HIRE"])
                
            return actions

    return SweepAgent()

def run_simulation(args):
    seed, tiles_per_worker = args
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    agent_instance = create_sweep_agent(tiles_per_worker)
    
    metrics = {
        "reward": 0,
        "harvest_count": 0,
        "worker_actions": {"MOVE": 0, "PRODUCTIVE": 0, "IDLE": 0},
        "water_backlog": []
    }
    
    def wrapper(obs, cfg=None):
        if not isinstance(obs, dict): return agent_instance(obs)
        
        state = ObservationParser.parse(obs)
        my_farm = state.my_farm
        
        water_backlog = 0
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                if tile.is_plant() and not tile.watered_today:
                    water_backlog += 1
                    
        metrics["water_backlog"].append(water_backlog)
        
        actions = agent_instance(obs)
        all_units = [my_farm.farmer] + list(my_farm.hands)
        
        unit_acts = [actions.get("farmer", ["PASS"])] + actions.get("hands", [])
        for act in unit_acts:
            if not act: continue
            a = act[0]
            if a in ["NORTH", "SOUTH", "EAST", "WEST"]: 
                metrics["worker_actions"]["MOVE"] += 1
            elif a == "PASS": 
                metrics["worker_actions"]["IDLE"] += 1
            else: 
                metrics["worker_actions"]["PRODUCTIVE"] += 1
                
            if a == "HARVEST": metrics["harvest_count"] += 1
            
        return actions

    steps = env.run([wrapper, "pass"])
    metrics["reward"] = steps[-1][0].reward
    
    # Calculate averages
    total_actions = sum(metrics["worker_actions"].values())
    move_pct = metrics["worker_actions"]["MOVE"] / max(1, total_actions)
    idle_pct = metrics["worker_actions"]["IDLE"] / max(1, total_actions)
    avg_water_backlog = sum(metrics["water_backlog"])/len(metrics["water_backlog"]) if metrics["water_backlog"] else 0
    
    return {
        "reward": metrics["reward"],
        "harvest_count": metrics["harvest_count"],
        "move_pct": move_pct,
        "idle_pct": idle_pct,
        "avg_water_backlog": avg_water_backlog
    }

def main():
    seeds = list(range(42, 62)) # 20 seeds for test run
    params = [8, 10, 12, 14, 16, 18, 20]
    
    print(f"{'Tiles/Worker':<15} | {'Mean Reward':<15} | {'Harvests':<10} | {'Move %':<10} | {'Idle %':<10} | {'Water Backlog'}")
    print("-" * 80)
    
    results_by_param = {}
    
    for tpw in params:
        args = [(s, tpw) for s in seeds]
        with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
            results = pool.map(run_simulation, args)
            
        mean_reward = statistics.mean([r["reward"] for r in results])
        mean_harvests = statistics.mean([r["harvest_count"] for r in results])
        mean_move = statistics.mean([r["move_pct"] for r in results])
        mean_idle = statistics.mean([r["idle_pct"] for r in results])
        mean_water = statistics.mean([r["avg_water_backlog"] for r in results])
        
        results_by_param[tpw] = {
            "reward": mean_reward,
            "harvests": mean_harvests,
            "move_pct": mean_move,
            "idle_pct": mean_idle,
            "water_backlog": mean_water
        }
        
        print(f"{tpw:<15} | ${mean_reward:<14.2f} | {mean_harvests:<10.1f} | {mean_move*100:<8.1f}% | {mean_idle*100:<8.1f}% | {mean_water:.2f}")

    with open("sweep_results.json", "w") as f:
        json.dump(results_by_param, f, indent=2)
        
    print("\nSweep complete. Results saved to sweep_results.json")

if __name__ == "__main__":
    main()
