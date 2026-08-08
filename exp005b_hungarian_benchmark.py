import sys
import os
import multiprocessing
import statistics
import time
import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser, Position
from fieldops.constants import CROP_DATA, SHED_ADJACENT_TILES
from fieldops.agent import MiniMelonAgent, _choose_movement, _distance

class HungarianAgent(MiniMelonAgent):
    def __call__(self, obs: dict) -> dict:
        actions = super().__call__(obs)
        if not isinstance(obs, dict) or (hasattr(obs, 'step') and obs.step > 718): 
            return actions
            
        state = ObservationParser.parse(obs)
        my_farm = state.my_farm
        
        max_melon_day = CROP_DATA["MELON"]["max_yield_day"]
        max_carrot_day = CROP_DATA["CARROT"]["max_yield_day"]
        
        unwatered_tiles = []
        harvestable_tiles = []
        empty_tiles = []
        
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                pos = Position(x=x, y=y)
                if tile.kind == "PLANT":
                    max_day = max_melon_day if tile.crop == "MELON" else max_carrot_day
                    if tile.planted_day is not None and (state.day - tile.planted_day) >= max_day:
                        harvestable_tiles.append(pos)
                    elif not tile.watered_today:
                        unwatered_tiles.append(pos)
                elif tile.is_empty():
                    empty_tiles.append(pos)
                    
        shed_tiles = [Position(x=x, y=y) for x, y in SHED_ADJACENT_TILES]
        all_units = [my_farm.farmer] + list(my_farm.hands)
        available_units = list(all_units)
        
        unit_actions_map = {id(u): ["PASS"] for u in all_units}
        targeted_tiles = set()
        
        def assign_hungarian(targets, action_label):
            nonlocal available_units
            valid_targets = [p for p in targets if p not in targeted_tiles]
            if not available_units or not valid_targets:
                return
                
            cost_matrix = np.zeros((len(available_units), len(valid_targets)))
            for i, u in enumerate(available_units):
                for j, t in enumerate(valid_targets):
                    cost_matrix[i, j] = _distance(u.position, t)
                    
            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            assigned_u = []
            for r, c in zip(row_ind, col_ind):
                u = available_units[r]
                t = valid_targets[c]
                targeted_tiles.add(t)
                if u.position == t:
                    unit_actions_map[id(u)] = [action_label]
                else:
                    unit_actions_map[id(u)] = [_choose_movement(u.position, t)]
                assigned_u.append(u)
                
            for u in assigned_u:
                available_units.remove(u)

        assign_hungarian(unwatered_tiles, "WATER")
        assign_hungarian(harvestable_tiles, "HARVEST")
        
        drop_units = [u for u in available_units if any(count > 0 for item, count in u.inventory.items.items() if item != "FERTILIZER")]
        for u in drop_units:
            target = min(shed_tiles, key=lambda p: _distance(u.position, p))
            if u.position in shed_tiles:
                unit_actions_map[id(u)] = ["DROP"]
            else:
                unit_actions_map[id(u)] = [_choose_movement(u.position, target)]
            available_units.remove(u)
            
        seed_reserves = {}
        for u in list(available_units):
            valid_empty = [p for p in empty_tiles if p not in targeted_tiles]
            if valid_empty:
                best_seed_crop = None
                best_seed_profit = -1
                
                if my_farm.seeds:
                    for crop_name, count in my_farm.seeds.items():
                        reserved = seed_reserves.get(crop_name, 0)
                        if count - reserved > 0:
                            data = CROP_DATA.get(crop_name)
                            if data and state.day + data["max_yield_day"] <= 29:
                                profit = data["base_price"] * data["max_yield_unf"] - data["seed_cost"]
                                if profit > best_seed_profit:
                                    best_seed_profit = profit
                                    best_seed_crop = crop_name
                
                if best_seed_crop is not None:
                    target = min(valid_empty, key=lambda p: _distance(u.position, p))
                    targeted_tiles.add(target)
                    seed_reserves[best_seed_crop] = seed_reserves.get(best_seed_crop, 0) + 1
                    if u.position == target:
                        unit_actions_map[id(u)] = ["PLANT", best_seed_crop]
                    else:
                        unit_actions_map[id(u)] = [_choose_movement(u.position, target)]
                    available_units.remove(u)
                    
        actions["farmer"] = unit_actions_map[id(my_farm.farmer)]
        actions["hands"] = [unit_actions_map[id(u)] for u in my_farm.hands]
        return actions

def run_simulation(args):
    seed, is_champ = args
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    
    agent_instance = MiniMelonAgent() if is_champ else HungarianAgent()
    
    metrics = {
        "reward": 0,
        "runtime": 0.0,
        "cputime": 0.0,
        "worker_travel": 0,
        "water_backlog": 0,
        "harvest_latencies": [],
        "replant_delays": []
    }
    
    mature_times = {}
    empty_times = {}
    
    def wrapper(obs, cfg=None):
        if not isinstance(obs, dict) or (hasattr(obs, 'step') and obs.step > 718):
            return agent_instance(obs)
            
        try:
            state = ObservationParser.parse(obs)
            my_farm = state.my_farm
            step = obs.step
            
            unwatered = 0
            for y, row in enumerate(my_farm.tiles):
                for x, tile in enumerate(row):
                    pos = (x, y)
                    if tile.kind == "PLANT":
                        if not tile.watered_today:
                            unwatered += 1
                        
                        max_day = 4 if tile.crop == "MELON" else 4
                        is_mature = tile.planted_day is not None and (state.day - tile.planted_day) >= max_day
                        if is_mature:
                            if pos not in mature_times:
                                mature_times[pos] = step
                        if pos in empty_times:
                            metrics["replant_delays"].append(step - empty_times[pos])
                            del empty_times[pos]
                            
                    elif tile.is_empty():
                        if pos in mature_times:
                            metrics["harvest_latencies"].append(step - mature_times[pos])
                            del mature_times[pos]
                        if pos not in empty_times:
                            empty_times[pos] = step
                            
            metrics["water_backlog"] += unwatered
            
            t0 = time.perf_counter()
            c0 = time.process_time()
            
            actions = agent_instance(obs)
            
            t1 = time.perf_counter()
            c1 = time.process_time()
            
            metrics["runtime"] += (t1 - t0)
            metrics["cputime"] += (c1 - c0)
            
            all_acts = [actions.get("farmer", ["PASS"])] + actions.get("hands", [])
            moves = sum(1 for a in all_acts if a and a[0] in ("NORTH", "SOUTH", "EAST", "WEST"))
            metrics["worker_travel"] += moves
            
            return actions
        except Exception:
            return agent_instance(obs)

    steps = env.run([wrapper, "pass"])
    if steps and steps[-1] and steps[-1][0]:
        metrics["reward"] = steps[-1][0].reward
        
    metrics["water_backlog"] = metrics["water_backlog"] / 720.0
    return {"seed": seed, "metrics": metrics}

def main():
    seeds = list(range(700, 800)) # 100 seeds for validation
    print("EXP-005B: Hungarian Assignment Benchmark")
    
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        champ_results = pool.map(run_simulation, [(s, True) for s in seeds])
        
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        test_results = pool.map(run_simulation, [(s, False) for s in seeds])
        
    def agg(results, key): return [r["metrics"][key] for r in results]
    def flat_agg(results, key): return [i for r in results for i in r["metrics"][key]]
    
    c_rewards = agg(champ_results, "reward")
    t_rewards = agg(test_results, "reward")
    
    c_mean = statistics.mean(c_rewards)
    t_mean = statistics.mean(t_rewards)
    delta = t_mean - c_mean
    
    wins = sum(1 for c, t in zip(c_rewards, t_rewards) if t > c)
    win_rate = wins / len(seeds)
    
    print("\n=========================================================")
    print("Benchmark Results")
    print("=========================================================")
    print(f"Champion Mean:   ${c_mean:.2f}")
    print(f"Hungarian Mean:  ${t_mean:.2f}")
    print(f"Delta:           ${delta:+.2f}")
    print(f"Win Rate:        {win_rate*100:.1f}%")
    
    print("\n=========================================================")
    print("Diagnostic Telemetry (Averages)")
    print("=========================================================")
    c_trav = statistics.mean(agg(champ_results, "worker_travel"))
    t_trav = statistics.mean(agg(test_results, "worker_travel"))
    print(f"Worker Travel:         {c_trav:.1f} steps -> {t_trav:.1f} steps")
    
    c_lat = statistics.mean(flat_agg(champ_results, "harvest_latencies")) if flat_agg(champ_results, "harvest_latencies") else 0
    t_lat = statistics.mean(flat_agg(test_results, "harvest_latencies")) if flat_agg(test_results, "harvest_latencies") else 0
    print(f"Harvest Latency:       {c_lat:.2f} hrs   -> {t_lat:.2f} hrs")
    
    c_rep = statistics.mean(flat_agg(champ_results, "replant_delays")) if flat_agg(champ_results, "replant_delays") else 0
    t_rep = statistics.mean(flat_agg(test_results, "replant_delays")) if flat_agg(test_results, "replant_delays") else 0
    print(f"Harvest->Replant:      {c_rep:.2f} hrs   -> {t_rep:.2f} hrs")
    
    c_wat = statistics.mean(agg(champ_results, "water_backlog"))
    t_wat = statistics.mean(agg(test_results, "water_backlog"))
    print(f"Water Backlog (avg):   {c_wat:.2f} plants -> {t_wat:.2f} plants")
    
    print("\n=========================================================")
    print("Performance Cost (Total per Game)")
    print("=========================================================")
    c_cpu = statistics.mean(agg(champ_results, "cputime"))
    t_cpu = statistics.mean(agg(test_results, "cputime"))
    print(f"CPU Time:              {c_cpu:.3f}s -> {t_cpu:.3f}s")
    
    c_run = statistics.mean(agg(champ_results, "runtime"))
    t_run = statistics.mean(agg(test_results, "runtime"))
    print(f"Wall Time:             {c_run:.3f}s -> {t_run:.3f}s")
    
    print("\n=========================================================")
    print("Decision")
    print("=========================================================")
    if delta < 500:
        print("TERMINATE EXP-005.")
    elif delta <= 1500:
        print("Proceed to Hybrid Assignment.")
    else:
        print("Proceed to full assignment research.")

if __name__ == "__main__":
    main()
