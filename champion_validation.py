import sys
import os
import multiprocessing
import statistics
import math
import json
import importlib

sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser
from fieldops.constants import CROP_DATA

def create_sweep_agent(tiles_per_worker=12):
    import fieldops.agent
    importlib.reload(fieldops.agent)
    from fieldops.agent import MiniMelonAgent

    class SweepAgent(MiniMelonAgent):
        def __call__(self, obs: dict) -> dict:
            if not isinstance(obs, dict): return super().__call__(obs)
            state = ObservationParser.parse(obs)
            my_farm = state.my_farm
            actions = super().__call__(obs)
            actions["market"] = [a for a in actions["market"] if a[0] != "HIRE"]
            
            quads_unlocked = len(my_farm.unlocked_quadrants)
            total_tiles = quads_unlocked * 25
            target_hands = (total_tiles // tiles_per_worker) - 1
            target_hands = max(0, target_hands)
            
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
        "water_backlog": [],
        "worker_hiring_cost": 0,
        "land_purchase_timing": []
    }
    
    def wrapper(obs, cfg=None):
        if not isinstance(obs, dict): return agent_instance(obs)
        step = obs.get("step", 0)
        state = ObservationParser.parse(obs)
        my_farm = state.my_farm
        
        water_backlog = 0
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                if tile.is_plant() and not tile.watered_today:
                    water_backlog += 1
        metrics["water_backlog"].append(water_backlog)
        
        actions = agent_instance(obs)
        
        for ma in actions.get("market", []):
            if ma[0] == "HIRE":
                # We can't perfectly track fibonacci without knowing exact hire state, 
                # but we track it by observing cash drop if we wanted to. We'll simplify.
                pass
            if ma[0] == "BUY_LAND":
                metrics["land_purchase_timing"].append(step)

        all_units = [my_farm.farmer] + list(my_farm.hands)
        unit_acts = [actions.get("farmer", ["PASS"])] + actions.get("hands", [])
        for act in unit_acts:
            if not act: continue
            a = act[0]
            if a in ["NORTH", "SOUTH", "EAST", "WEST"]: metrics["worker_actions"]["MOVE"] += 1
            elif a == "PASS": metrics["worker_actions"]["IDLE"] += 1
            else: metrics["worker_actions"]["PRODUCTIVE"] += 1
            if a == "HARVEST": metrics["harvest_count"] += 1
            
        return actions

    steps = env.run([wrapper, "pass"])
    metrics["reward"] = steps[-1][0].reward
    
    total_actions = sum(metrics["worker_actions"].values())
    move_pct = metrics["worker_actions"]["MOVE"] / max(1, total_actions)
    idle_pct = metrics["worker_actions"]["IDLE"] / max(1, total_actions)
    avg_water_backlog = sum(metrics["water_backlog"])/len(metrics["water_backlog"]) if metrics["water_backlog"] else 0
    
    return {
        "seed": seed,
        "tiles_per_worker": tiles_per_worker,
        "reward": metrics["reward"],
        "harvest_count": metrics["harvest_count"],
        "move_pct": move_pct,
        "idle_pct": idle_pct,
        "avg_water_backlog": avg_water_backlog,
        "land_purchase_timing": metrics["land_purchase_timing"]
    }

def welchs_t_test(data1, data2):
    n1, n2 = len(data1), len(data2)
    m1, m2 = statistics.mean(data1), statistics.mean(data2)
    v1, v2 = statistics.variance(data1), statistics.variance(data2)
    
    t_stat = (m1 - m2) / math.sqrt(v1/n1 + v2/n2)
    df = (v1/n1 + v2/n2)**2 / ((v1/n1)**2 / (n1-1) + (v2/n2)**2 / (n2-1))
    return t_stat, df

def main():
    seeds = list(range(100, 200)) # 100 seeds for statistical validation
    
    # Run Champion (20)
    args_champ = [(s, 20) for s in seeds]
    print("Running Champion (20 tiles/worker)...", flush=True)
    results_champ = []
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        for i, res in enumerate(pool.imap_unordered(run_simulation, args_champ)):
            results_champ.append(res)
            if (i+1) % 10 == 0:
                print(f"  Champion progress: {i+1}/{len(seeds)}", flush=True)
        
    # Run Challenger (14)
    args_chall = [(s, 14) for s in seeds]
    print("Running Challenger (14 tiles/worker)...", flush=True)
    results_chall = []
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        for i, res in enumerate(pool.imap_unordered(run_simulation, args_chall)):
            results_chall.append(res)
            if (i+1) % 10 == 0:
                print(f"  Challenger progress: {i+1}/{len(seeds)}", flush=True)
        
    # Match seeds exactly for paired comparison
    results_champ.sort(key=lambda x: x["seed"])
    results_chall.sort(key=lambda x: x["seed"])
        
    # Stats
    champ_rewards = [r["reward"] for r in results_champ]
    chall_rewards = [r["reward"] for r in results_chall]
    
    win_count = sum(1 for c, h in zip(champ_rewards, chall_rewards) if h > c)
    win_rate = win_count / len(seeds)
    
    t_stat, df = welchs_t_test(chall_rewards, champ_rewards)
    
    # Dump to JSON
    report = {
        "champion": {
            "mean_reward": statistics.mean(champ_rewards),
            "median_reward": statistics.median(champ_rewards),
            "std_dev": statistics.stdev(champ_rewards),
            "min_reward": min(champ_rewards),
            "max_reward": max(champ_rewards),
            "mean_harvests": statistics.mean([r["harvest_count"] for r in results_champ]),
            "mean_move_pct": statistics.mean([r["move_pct"] for r in results_champ]),
            "mean_idle_pct": statistics.mean([r["idle_pct"] for r in results_champ]),
            "mean_water_backlog": statistics.mean([r["avg_water_backlog"] for r in results_champ])
        },
        "challenger": {
            "mean_reward": statistics.mean(chall_rewards),
            "median_reward": statistics.median(chall_rewards),
            "std_dev": statistics.stdev(chall_rewards),
            "min_reward": min(chall_rewards),
            "max_reward": max(chall_rewards),
            "mean_harvests": statistics.mean([r["harvest_count"] for r in results_chall]),
            "mean_move_pct": statistics.mean([r["move_pct"] for r in results_chall]),
            "mean_idle_pct": statistics.mean([r["idle_pct"] for r in results_chall]),
            "mean_water_backlog": statistics.mean([r["avg_water_backlog"] for r in results_chall])
        },
        "comparison": {
            "win_rate": win_rate,
            "t_statistic": t_stat,
            "degrees_of_freedom": df,
            "mean_diff": statistics.mean(chall_rewards) - statistics.mean(champ_rewards)
        }
    }
    
    with open("validation_report.json", "w") as f:
        json.dump(report, f, indent=2)
        
    print("Validation complete. Report saved.")

if __name__ == "__main__":
    main()
