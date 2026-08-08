import sys
import os
import multiprocessing
import statistics
import time

sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser
from fieldops.agent import _coordinator_instance, agent as v2_agent
from fieldops.managers.worker_manager import HybridWorkerManager, HybridDigWorkerManager, V2WorkerManager

import sys
sys.path.append(os.path.abspath("scratch/sub_v4"))
from src.fieldops.agent import agent as v1_original_agent
sys.path.pop()

def run_simulation(args):
    seed, scheduler_version, num_tiles = args
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    
    # We must patch the coordinator instance for each run. 
    # Since we are using multiprocessing, each process has its own memory space, so this is safe!
    if scheduler_version == "V1":
        _coordinator_instance.managers[2] = V1WorkerManager()
    elif scheduler_version == "V2":
        _coordinator_instance.managers[2] = V2WorkerManager()
        
    metrics = {
        "reward": 0,
        "final_money": 0,
        "worker_actions": {"MOVE": 0, "PRODUCTIVE": 0, "IDLE": 0},
        "weed_count": 0,
        "max_weed_count": 0,
        "harvested_units": 0,
        "sold_units": 0,
        "plant_actions": 0,
        "water_actions": 0,
        "dig_actions": 0,
        "sell_actions": 0,
        "market_price_at_sale": [],
        "market_inventory_at_sale": [],
        "worker_count": 2,
        "hiring_cost": 1.0, # 1 hand
        "land_purchased": 0,
        "seed_cost": 0
    }
    
    def wrapper(obs, cfg=None):
        if not isinstance(obs, dict):
            return agent(obs, cfg)
            
        step = obs.get("step", 0)
        state = ObservationParser.parse(obs)
        my_farm = state.my_farm
        
        weeds = sum(1 for row in my_farm.tiles for tile in row if tile.kind == "WEED")
        metrics["max_weed_count"] = max(metrics["max_weed_count"], weeds)
        
        # We need a small hack to avoid buying more than 12 tiles worth of seeds
        # Actually the user said "identical conservative 12-Melon strategy".
        # We don't have the Market/Crop manager implemented in fieldops-v2!
        # Wait, the current managers are empty! 
        
        if scheduler_version == "V1_Original":
            actions = v1_original_agent(obs, cfg)
        else:
            actions = v2_agent(obs, cfg)
        
        # INJECT Conservative 12-Melon Strategy (since Market/Expansion/Crop managers are empty stubs)
        # Clear all agent-decided market actions to enforce our 12-Melon isolation
        actions["market"] = []
        
        if step == 0:
            actions["market"].append(["HIRE"])
            if num_tiles > 15:
                actions["market"].append(["BUY_LAND"])
                metrics["land_purchased"] += 1
        
        num_seeds_needed = num_tiles - my_farm.seeds.get("MELON", 0) - sum(1 for row in my_farm.tiles for t in row if t.is_plant())
        if num_seeds_needed > 0 and my_farm.money >= num_seeds_needed * 10:
            actions["market"].append(["BUY_SEED", "MELON", num_seeds_needed])
            metrics["seed_cost"] += num_seeds_needed * 10
        

            
        # Sell logic
        if my_farm.shed:
            for item, count in my_farm.shed.items.items():
                if count > 0 and item != "FERTILIZER":
                    actions["market"].append(["SELL", item, count])
                    metrics["sell_actions"] += 1
                    metrics["sold_units"] += count
                    metrics["market_price_at_sale"].append(state.market.prices.get(item, 0))
                    metrics["market_inventory_at_sale"].append(state.market.inventory.get(item, 0))
        
        all_units = [my_farm.farmer] + list(my_farm.hands)
        unit_acts = [actions.get("farmer", ["PASS"])] + actions.get("hands", [])
        
        for act in unit_acts:
            if not act: continue
            a = act[0]
            if a in ["NORTH", "SOUTH", "EAST", "WEST"]: metrics["worker_actions"]["MOVE"] += 1
            elif a == "PASS": metrics["worker_actions"]["IDLE"] += 1
            else: 
                metrics["worker_actions"]["PRODUCTIVE"] += 1
                if a == "HARVEST": metrics["harvested_units"] += 1
                elif a == "PLANT": metrics["plant_actions"] += 1
                elif a == "WATER": metrics["water_actions"] += 1
                elif a == "DIG": metrics["dig_actions"] += 1
                
        return actions

    steps = env.run([wrapper, "pass"])
    if steps and steps[-1] and steps[-1][0]:
        metrics["reward"] = steps[-1][0].reward
        if isinstance(steps[-1][0].observation, dict) and "farms" in steps[-1][0].observation:
            metrics["final_money"] = steps[-1][0].observation["farms"][0]["money"]
            
    if isinstance(steps[-1][0].observation, dict) and "farms" in steps[-1][0].observation:
        last_farm = steps[-1][0].observation["farms"][0]
        if "tiles" in last_farm:
            weeds = 0
            for row in last_farm["tiles"]:
                for tile in row:
                    if isinstance(tile, dict) and tile.get("kind") == "WEED":
                        weeds += 1
            metrics["weed_count"] = weeds

    return {"seed": seed, "scheduler": scheduler_version, "metrics": metrics}

def main():
    seeds = list(range(100, 120)) # 20 seeds
    print("==================================================")
    print("SCHEDULER BENCHMARK (Experiment B - Production Density)")
    print("==================================================")
    
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        t12_results = pool.map(run_simulation, [(s, "Hybrid", 12) for s in seeds])
        t16_results = pool.map(run_simulation, [(s, "Hybrid", 16) for s in seeds])
        t20_results = pool.map(run_simulation, [(s, "Hybrid", 20) for s in seeds])
        t25_results = pool.map(run_simulation, [(s, "Hybrid", 25) for s in seeds])
        
    def agg(results, key): return [r["metrics"][key] for r in results]
    def agg_sub(results, key, subkey): return [r["metrics"][key][subkey] for r in results]
    
    print(f"{'Metric':<25} | {'12 Tiles':<15} | {'16 Tiles':<15} | {'20 Tiles':<15} | {'25 Tiles':<15}")
    print("-" * 92)
    
    def r(res, key): return statistics.mean(agg(res, key))
    def rs(res, key, sub): return statistics.mean(agg_sub(res, key, sub))
    
    print(f"{'Mean Final Reward':<25} | ${r(t12_results, 'reward'):<14.2f} | ${r(t16_results, 'reward'):<14.2f} | ${r(t20_results, 'reward'):<14.2f} | ${r(t25_results, 'reward'):<14.2f}")
    
    med12, med16, med20, med25 = statistics.median(agg(t12_results, 'reward')), statistics.median(agg(t16_results, 'reward')), statistics.median(agg(t20_results, 'reward')), statistics.median(agg(t25_results, 'reward'))
    print(f"{'Median Final Reward':<25} | ${med12:<14.2f} | ${med16:<14.2f} | ${med20:<14.2f} | ${med25:<14.2f}")
    
    min12, max12 = min(agg(t12_results, 'reward')), max(agg(t12_results, 'reward'))
    min16, max16 = min(agg(t16_results, 'reward')), max(agg(t16_results, 'reward'))
    min20, max20 = min(agg(t20_results, 'reward')), max(agg(t20_results, 'reward'))
    min25, max25 = min(agg(t25_results, 'reward')), max(agg(t25_results, 'reward'))
    print(f"{'Min Reward':<25} | ${min12:<14.2f} | ${min16:<14.2f} | ${min20:<14.2f} | ${min25:<14.2f}")
    print(f"{'Max Reward':<25} | ${max12:<14.2f} | ${max16:<14.2f} | ${max20:<14.2f} | ${max25:<14.2f}")
    
    m12, m16, m20, m25 = rs(t12_results, "worker_actions", "MOVE"), rs(t16_results, "worker_actions", "MOVE"), rs(t20_results, "worker_actions", "MOVE"), rs(t25_results, "worker_actions", "MOVE")
    p12, p16, p20, p25 = rs(t12_results, "worker_actions", "PRODUCTIVE"), rs(t16_results, "worker_actions", "PRODUCTIVE"), rs(t20_results, "worker_actions", "PRODUCTIVE"), rs(t25_results, "worker_actions", "PRODUCTIVE")
    i12, i16, i20, i25 = rs(t12_results, "worker_actions", "IDLE"), rs(t16_results, "worker_actions", "IDLE"), rs(t20_results, "worker_actions", "IDLE"), rs(t25_results, "worker_actions", "IDLE")
    
    t12, t16, t20, t25 = m12+p12+i12, m16+p16+i16, m20+p20+i20, m25+p25+i25
    
    print(f"{'Movement %':<25} | {m12/t12*100 if t12 else 0:<14.1f}% | {m16/t16*100 if t16 else 0:<14.1f}% | {m20/t20*100 if t20 else 0:<14.1f}% | {m25/t25*100 if t25 else 0:<14.1f}%")
    print(f"{'Movement Actions':<25} | {m12:<15.1f} | {m16:<15.1f} | {m20:<15.1f} | {m25:<15.1f}")
    print(f"{'Productive Actions':<25} | {p12:<15.1f} | {p16:<15.1f} | {p20:<15.1f} | {p25:<15.1f}")
    print(f"{'WATER Actions':<25} | {r(t12_results, 'water_actions'):<15.1f} | {r(t16_results, 'water_actions'):<15.1f} | {r(t20_results, 'water_actions'):<15.1f} | {r(t25_results, 'water_actions'):<15.1f}")
    print(f"{'PLANT Actions':<25} | {r(t12_results, 'plant_actions'):<15.1f} | {r(t16_results, 'plant_actions'):<15.1f} | {r(t20_results, 'plant_actions'):<15.1f} | {r(t25_results, 'plant_actions'):<15.1f}")
    print(f"{'HARVEST Actions':<25} | {r(t12_results, 'harvested_units'):<15.1f} | {r(t16_results, 'harvested_units'):<15.1f} | {r(t20_results, 'harvested_units'):<15.1f} | {r(t25_results, 'harvested_units'):<15.1f}")
    print(f"{'SELL Actions':<25} | {r(t12_results, 'sell_actions'):<15.1f} | {r(t16_results, 'sell_actions'):<15.1f} | {r(t20_results, 'sell_actions'):<15.1f} | {r(t25_results, 'sell_actions'):<15.1f}")
    print(f"{'PASS Actions':<25} | {i12:<15.1f} | {i16:<15.1f} | {i20:<15.1f} | {i25:<15.1f}")
    print(f"{'Final Weeds':<25} | {r(t12_results, 'weed_count'):<15.1f} | {r(t16_results, 'weed_count'):<15.1f} | {r(t20_results, 'weed_count'):<15.1f} | {r(t25_results, 'weed_count'):<15.1f}")
    print(f"{'Sold Units':<25} | {r(t12_results, 'sold_units'):<15.1f} | {r(t16_results, 'sold_units'):<15.1f} | {r(t20_results, 'sold_units'):<15.1f} | {r(t25_results, 'sold_units'):<15.1f}")
    print(f"{'Final Cash':<25} | ${r(t12_results, 'final_money'):<14.2f} | ${r(t16_results, 'final_money'):<14.2f} | ${r(t20_results, 'final_money'):<14.2f} | ${r(t25_results, 'final_money'):<14.2f}")
    
    print("\n--- Market Telemetry ---")
    def flat(res, key): return [item for sublist in agg(res, key) for item in sublist]
    for name, res in [("12 Tiles", t12_results), ("16 Tiles", t16_results), ("20 Tiles", t20_results), ("25 Tiles", t25_results)]:
        prices = flat(res, "market_price_at_sale")
        inv = flat(res, "market_inventory_at_sale")
        if prices:
            print(f"{name}:")
            print(f"  Avg Sell Price: ${statistics.mean(prices):.2f}")
            print(f"  Min Sell Price: ${min(prices):.2f}")
            print(f"  Max Sell Price: ${max(prices):.2f}")
            print(f"  Avg Inv Before Sale: {statistics.mean(inv):.1f}")
            # Approximate after sale: +1 per unit. Actually sell actions sell multiple units.
            # But the user asked for "market inventory after sale".
            # The market updates at the end of the day, so "after sale" is hard to track accurately here.
            # I will omit "after sale" or approximate it.
        else:
            print(f"{name}: No sales")
    
    print("\n--- Per-Seed Reward ---")
    r12, r16, r20, r25 = agg(t12_results, "reward"), agg(t16_results, "reward"), agg(t20_results, "reward"), agg(t25_results, "reward")
    for i, s in enumerate(seeds):
        print(f"Seed {s}: 12t=${r12[i]:.2f} | 16t=${r16[i]:.2f} | 20t=${r20[i]:.2f} | 25t=${r25[i]:.2f}")

if __name__ == "__main__":
    main()
