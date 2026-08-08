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

def run_economic_audit(seed):
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    agent = MiniMelonAgent()
    
    metrics = {
        "regrets": [],
        "task_regrets": defaultdict(list),
        "phase_regrets": {"Early Game": [], "Mid Game": [], "Late Game": []},
        "distribution": {"0": 0, "1-2": 0, "3-5": 0, "6-10": 0, ">10": 0}
    }
    
    def wrapper(obs, cfg=None):
        if hasattr(obs, 'step') and obs.step > 718:
            return agent(obs)
        try:
            state = ObservationParser.parse(obs)
            my_farm = state.my_farm
            day = state.day
            
            game_phase = "Early Game"
            if day >= 20:
                game_phase = "Late Game"
            elif day >= 10:
                game_phase = "Mid Game"
            
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
            
            # Helper to process phases
            def process_phase(targets, phase_name):
                if targets and available_units:
                    g_cost, assigned = calc_greedy(available_units, targets)
                    o_cost = calc_optimal(available_units, targets)
                    regret = g_cost - o_cost
                    
                    if regret == 0:
                        metrics["distribution"]["0"] += 1
                    elif regret <= 2:
                        metrics["distribution"]["1-2"] += 1
                    elif regret <= 5:
                        metrics["distribution"]["3-5"] += 1
                    elif regret <= 10:
                        metrics["distribution"]["6-10"] += 1
                    else:
                        metrics["distribution"][">10"] += 1
                        
                    if regret > 0:
                        metrics["regrets"].append(regret)
                        metrics["task_regrets"][phase_name].append(regret)
                        metrics["phase_regrets"][game_phase].append(regret)
                        
                    for u in assigned: available_units.remove(u)
            
            process_phase(unwatered, "WATER")
            process_phase(harvestable, "HARVEST")
            
            drop_units = [u for u in available_units if any(c > 0 for i, c in u.inventory.items.items() if i != "FERTILIZER")]
            if drop_units:
                g_cost, assigned = calc_greedy(drop_units, shed)
                o_cost = calc_optimal(drop_units, shed)
                regret = g_cost - o_cost
                
                if regret == 0:
                    metrics["distribution"]["0"] += 1
                elif regret <= 2:
                    metrics["distribution"]["1-2"] += 1
                elif regret <= 5:
                    metrics["distribution"]["3-5"] += 1
                elif regret <= 10:
                    metrics["distribution"]["6-10"] += 1
                else:
                    metrics["distribution"][">10"] += 1
                    
                if regret > 0:
                    metrics["regrets"].append(regret)
                    metrics["task_regrets"]["DROP"].append(regret)
                    metrics["phase_regrets"][game_phase].append(regret)
                for u in assigned: available_units.remove(u)
                
            if my_farm.seeds:
                process_phase(empty, "PLANT")
                
        except Exception as e:
            pass
            
        return agent(obs)

    env.run([wrapper, "pass"])
    return metrics

def main():
    seeds = list(range(600, 620))
    print("EXP-005A.5: Counterfactual Assignment Analysis")
    
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        results = pool.map(run_economic_audit, seeds)
        
    all_regrets = []
    task_regrets = defaultdict(list)
    phase_regrets = {"Early Game": [], "Mid Game": [], "Late Game": []}
    distribution = {"0": 0, "1-2": 0, "3-5": 0, "6-10": 0, ">10": 0}
    
    for r in results:
        all_regrets.extend(r["regrets"])
        for k, v in r["task_regrets"].items():
            task_regrets[k].extend(v)
        for k, v in r["phase_regrets"].items():
            phase_regrets[k].extend(v)
        for k, v in r["distribution"].items():
            distribution[k] += v
            
    # Economic conversion constants
    melon = CROP_DATA["MELON"]
    profit = melon["base_price"] * melon["max_yield_unf"] - melon["seed_cost"]
    cycle_hours = melon["max_yield_day"] * 24
    base_ev_per_hour = profit / cycle_hours  # ~$4.93
    
    # Heuristic phase multipliers for delay severity
    # Delays in late game have a much higher chance of pushing a harvest off the Day 30 cliff.
    phase_multipliers = {
        "Early Game": 1.0,  # Plenty of slack
        "Mid Game": 2.5,    # Diminishing slack, cascading delays start to bite
        "Late Game": 6.0    # Razor-thin margins; a 1-hour delay often destroys a $1420 harvest
    }
    
    if not all_regrets:
        print("No regrets recorded.")
        return
        
    economic_regrets = []
    task_evs = defaultdict(float)
    phase_evs = defaultdict(float)
    
    # To compute stats properly, we need the exact economic value of every regret
    # Since we didn't store the exact phase of EVERY single regret in a flat list (just grouped them),
    # we'll compute phase totals and then build a synthesized flat list for median/p95 calculations.
    for phase in ["Early Game", "Mid Game", "Late Game"]:
        mult = phase_multipliers[phase]
        for r in phase_regrets[phase]:
            ev = r * base_ev_per_hour * mult
            economic_regrets.append(ev)
            phase_evs[phase] += ev
            
    # For tasks, we'll just use the global average multiplier to approximate their EV share
    avg_multiplier = sum(economic_regrets) / sum(r * base_ev_per_hour for r in all_regrets)
    for task, regs in task_regrets.items():
        task_evs[task] = sum(r * base_ev_per_hour * avg_multiplier for r in regs)
    
    mean_ev = statistics.mean(economic_regrets)
    median_ev = statistics.median(economic_regrets)
    p95_ev = np.percentile(economic_regrets, 95)
    max_ev = max(economic_regrets)
    
    total_ev = sum(economic_regrets)
    ev_per_seed = total_ev / len(seeds)
    
    print(f"\n=========================================================")
    print(f"Counterfactual Assignment Analysis (Phase-Adjusted)")
    print(f"=========================================================")
    print(f"Mean economic regret: ${mean_ev:.2f}")
    print(f"Median economic regret: ${median_ev:.2f}")
    print(f"95th percentile: ${p95_ev:.2f}")
    print(f"Worst case: ${max_ev:.2f}")
    print(f"Total estimated EV (all seeds): ${total_ev:.2f}")
    print(f"Total estimated EV (PER SEED): ${ev_per_seed:.2f}")
    
    print(f"\n=========================================================")
    print(f"Report by Game Phase (EV lost per seed)")
    print(f"=========================================================")
    for phase in ["Early Game", "Mid Game", "Late Game"]:
        print(f"{phase:<12} | ${(phase_evs[phase]/len(seeds)):.2f}")
        
    print(f"\n=========================================================")
    print(f"Report by Task (EV lost per seed)")
    print(f"=========================================================")
    for task in ["WATER", "HARVEST", "PLANT", "DROP"]:
        print(f"{task:<12} | ${(task_evs[task]/len(seeds)):.2f}")
        
    print(f"\n=========================================================")
    print(f"Assignment Regret Distribution")
    print(f"=========================================================")
    total_decisions = sum(distribution.values())
    for bin_k in ["0", "1-2", "3-5", "6-10", ">10"]:
        count = distribution[bin_k]
        pct = (count / total_decisions) * 100 if total_decisions else 0
        print(f"{bin_k:<10} | {count:6,} ({pct:4.1f}%)")
        
    print(f"\n=========================================================")
    print(f"If we replaced Greedy with mathematically optimal assignment,")
    print(f"what is the theoretical maximum increase in Final Money?")
    print(f"=========================================================")
    print(f"+${ev_per_seed:.0f}")
    
    print(f"\n=========================================================")
    print(f"Decision")
    print(f"=========================================================")
    if ev_per_seed < 500:
        print("TERMINATE EXP-005.")
    elif ev_per_seed <= 1500:
        print("Implement only Hybrid Assignment.")
    else:
        print("Proceed to full Hungarian/Auction benchmark.")

if __name__ == "__main__":
    main()
