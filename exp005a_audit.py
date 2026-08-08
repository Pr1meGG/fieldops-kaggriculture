import sys
import os
import multiprocessing
import json
import statistics
import numpy as np
from scipy.optimize import linear_sum_assignment
from collections import defaultdict

sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser, Position
from fieldops.constants import CROP_DATA, SHED_ADJACENT_TILES
from fieldops.agent import MiniMelonAgent

def _distance(p1, p2):
    return abs(p1.x - p2.x) + abs(p1.y - p2.y)

def calc_optimal(units, targets):
    if not units or not targets:
        return 0
    cost_matrix = np.zeros((len(units), len(targets)))
    for i, u in enumerate(units):
        for j, t in enumerate(targets):
            cost_matrix[i, j] = _distance(u.position, t)
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    return cost_matrix[row_ind, col_ind].sum()

def calc_greedy(units, targets):
    if not units or not targets:
        return 0, []
    cost = 0
    assigned_units = []
    available_targets = list(targets)
    for u in units:
        if not available_targets:
            break
        best_t = min(available_targets, key=lambda t: _distance(u.position, t))
        cost += _distance(u.position, best_t)
        available_targets.remove(best_t)
        assigned_units.append(u)
    return cost, assigned_units

def run_audit(seed):
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    agent = MiniMelonAgent()
    
    metrics = {
        "regrets": [],
        "task_regrets": defaultdict(list),
        "total_decisions": 0,
        "optimal_decisions": 0,
        "error": None
    }
    
    def wrapper(obs, cfg=None):
        if hasattr(obs, 'step') and obs.step > 718:
            return agent(obs)
        try:
            state = ObservationParser.parse(obs)
            my_farm = state.my_farm
            
            # We must replicate the agent's list generation to audit it
            max_melon_day = CROP_DATA["MELON"]["max_yield_day"]
            max_carrot_day = CROP_DATA["CARROT"]["max_yield_day"]
            
            unwatered = []
            harvestable = []
            empty = []
            
            for y, row in enumerate(my_farm.tiles):
                for x, tile in enumerate(row):
                    pos = Position(x=x, y=y)
                    if tile.kind == "PLANT":
                        max_day = max_melon_day if tile.crop == "MELON" else max_carrot_day
                        if tile.planted_day is not None and (state.day - tile.planted_day) >= max_day:
                            harvestable.append(pos)
                        elif not tile.watered_today:
                            unwatered.append(pos)
                    elif tile.is_empty():
                        empty.append(pos)
                        
            shed = [Position(x=x, y=y) for x, y in SHED_ADJACENT_TILES]
            
            all_units = [my_farm.farmer] + list(my_farm.hands)
            available_units = list(all_units)
            
            # 1. WATER
            if unwatered and available_units:
                g_cost, assigned = calc_greedy(available_units, unwatered)
                o_cost = calc_optimal(available_units, unwatered)
                regret = g_cost - o_cost
                metrics["regrets"].append(regret)
                metrics["task_regrets"]["WATER"].append(regret)
                metrics["total_decisions"] += 1
                if regret == 0: metrics["optimal_decisions"] += 1
                for u in assigned: available_units.remove(u)
                
            # 2. HARVEST
            if harvestable and available_units:
                g_cost, assigned = calc_greedy(available_units, harvestable)
                o_cost = calc_optimal(available_units, harvestable)
                regret = g_cost - o_cost
                metrics["regrets"].append(regret)
                metrics["task_regrets"]["HARVEST"].append(regret)
                metrics["total_decisions"] += 1
                if regret == 0: metrics["optimal_decisions"] += 1
                for u in assigned: available_units.remove(u)
                
            # 3. DROP
            drop_units = [u for u in available_units if any(c > 0 for i, c in u.inventory.items.items() if i != "FERTILIZER")]
            if drop_units:
                g_cost, assigned = calc_greedy(drop_units, shed)
                o_cost = calc_optimal(drop_units, shed)
                regret = g_cost - o_cost
                metrics["regrets"].append(regret)
                metrics["task_regrets"]["DROP"].append(regret)
                metrics["total_decisions"] += 1
                if regret == 0: metrics["optimal_decisions"] += 1
                for u in assigned: available_units.remove(u)
                
            # 4. PLANT
            if empty and available_units and my_farm.seeds:
                g_cost, assigned = calc_greedy(available_units, empty)
                o_cost = calc_optimal(available_units, empty)
                regret = g_cost - o_cost
                metrics["regrets"].append(regret)
                metrics["task_regrets"]["PLANT"].append(regret)
                metrics["total_decisions"] += 1
                if regret == 0: metrics["optimal_decisions"] += 1
                for u in assigned: available_units.remove(u)
        except Exception as e:
            import traceback
            metrics["error"] = traceback.format_exc()
            
        return agent(obs)

    steps = env.run([wrapper, "pass"])
    
    # Just in case, grab reward from last step
    if steps and steps[-1] and steps[-1][0]:
        print(f"Seed {seed} final reward: {steps[-1][0].reward}")
        
    return metrics

def main():
    seeds = list(range(600, 620))
    print("EXP-005A: Assignment Quality Audit (Greedy vs Optimal)")
    
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        results = pool.map(run_audit, seeds)
        
    all_regrets = []
    task_regrets = defaultdict(list)
    total_decisions = 0
    optimal_decisions = 0
    
    for r in results:
        if r.get("error") and "step 719" not in r["error"]:
            print(f"DEBUG CRASH: {r['error']}")
        all_regrets.extend(r["regrets"])
        for k, v in r["task_regrets"].items():
            task_regrets[k].extend(v)
        total_decisions += r["total_decisions"]
        optimal_decisions += r["optimal_decisions"]
        
    if not all_regrets:
        print("No assignment decisions recorded.")
        return
        
    mean_r = statistics.mean(all_regrets)
    median_r = statistics.median(all_regrets)
    max_r = max(all_regrets)
    pct_optimal = (optimal_decisions / total_decisions) * 100
    
    print(f"\n--- Global Audit ---")
    print(f"Total Scheduling Phases Evaluated: {total_decisions:,}")
    print(f"Mean Regret (Steps Wasted): {mean_r:.2f}")
    print(f"Median Regret: {median_r:.2f}")
    print(f"Max Regret: {max_r}")
    print(f"% Decisions Already Optimal: {pct_optimal:.1f}%\n")
    
    print("--- Regret By Task Type ---")
    for task in ["WATER", "HARVEST", "DROP", "PLANT"]:
        regrets = task_regrets[task]
        if regrets:
            print(f"{task:<10} | Mean: {statistics.mean(regrets):.2f} | Max: {max(regrets)}")
        else:
            print(f"{task:<10} | No data")
            
    print("\n--- Recommendation ---")
    if pct_optimal > 90.0:
        print("TERMINATE EXP-005: Greedy logic is already highly optimal. Low expected value from algorithmic overhaul.")
    else:
        print("PROCEED TO EXP-005B: Substantial regret detected. Hungarian/Auction routing implementation is justified.")
        
    with open("exp005a_audit_results.json", "w") as f:
        json.dump({
            "mean_regret": mean_r,
            "median_regret": median_r,
            "max_regret": max_r,
            "pct_optimal": pct_optimal,
            "task_regrets_mean": {k: statistics.mean(v) for k, v in task_regrets.items() if v}
        }, f, indent=2)

if __name__ == "__main__":
    main()
