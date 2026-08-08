import sys
import os
import multiprocessing
import statistics

sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser
from fieldops.constants import CROP_DATA
from fieldops.agent import MiniMelonAgent

def run_audit(seed):
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    agent = MiniMelonAgent()
    
    metrics = {
        "planting_opps_after_18": 0,
        "dynamic_non_melon_opps": 0,
        "skipped_opps": 0,
        "idle_workers_caused": 0,
    }
    
    def wrapper(obs, cfg=None):
        if hasattr(obs, 'step') and obs.step > 718:
            return agent(obs)
            
        try:
            state = ObservationParser.parse(obs)
            actions = agent(obs)
            
            if state.day > 18:
                my_farm = state.my_farm
                empty_tiles = sum(1 for row in my_farm.tiles for tile in row if tile.is_empty())
                
                if empty_tiles > 0:
                    metrics["planting_opps_after_18"] += empty_tiles
                    
                    # Replicate dynamic logic
                    best_profit = -1
                    best_crop = None
                    for crop_name, data in CROP_DATA.items():
                        if state.day + data["max_yield_day"] <= 29:
                            profit = data["base_price"] * data["max_yield_unf"] - data["seed_cost"]
                            if profit > best_profit:
                                best_profit = profit
                                best_crop = crop_name
                                
                    if best_crop and best_crop != "MELON":
                        metrics["dynamic_non_melon_opps"] += empty_tiles
                        
                    # How many were actually skipped by the agent?
                    all_acts = [actions.get("farmer", ["PASS"])] + actions.get("hands", [])
                    plants = sum(1 for act in all_acts if act and act[0] == "PLANT")
                    
                    skipped = empty_tiles - plants
                    if skipped > 0:
                        metrics["skipped_opps"] += skipped
                        
                    # Idle workers when there are empty tiles but no seeds
                    if skipped > 0:
                        idle = sum(1 for act in all_acts if act and act[0] == "PASS")
                        metrics["idle_workers_caused"] += idle
                        
            return actions
        except Exception:
            return agent(obs)

    env.run([wrapper, "pass"])
    return metrics

def main():
    seeds = list(range(900, 1000))
    print("Candidate 1 Audit: Late-Game Crop Hardcoding Bug")
    print("Running 100 seeds...")
    
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        results = pool.map(run_audit, seeds)
        
    def agg(key): return sum(r[key] for r in results)
    
    total_opps = agg("planting_opps_after_18")
    dynamic_opps = agg("dynamic_non_melon_opps")
    skipped = agg("skipped_opps")
    idle = agg("idle_workers_caused")
    
    avg_lost_harvests = (skipped / len(seeds)) / 4.0 # Carrots take 4 days, so roughly skipped tiles / 4
    
    print("\n=========================================================")
    print("Audit Results (Across 100 Seeds)")
    print("=========================================================")
    print(f"Planting opportunities after Day 18:              {total_opps:,}")
    print(f"Opps where dynamic logic chooses non-Melon:       {dynamic_opps:,}")
    print(f"Opps actually skipped due to override:            {skipped:,}")
    print(f"Idle workers caused by override:                  {idle:,}")
    print(f"\nEstimated lost harvests per seed:                 ~{avg_lost_harvests:,.1f} plants")

if __name__ == "__main__":
    main()
