"""
Experiment J3 — Spatial Locality
================================
Isolated research script to test if planting in a compact cluster
(closest to shed) improves overall reward vs the default scattered
planting (closest to worker).

Fixed parameters:
- 2 workers
- 12 Melons
- V1 Unit-Centric base logic
"""

import os
import sys
import statistics
import json

sys.path.insert(0, os.path.abspath("src"))

from kaggle_environments import make
from fieldops.state import ObservationParser, Position
from fieldops.constants import CROP_DATA, SHED_ADJACENT_TILES
from fieldops.managers.worker_manager import (
    HybridWorkerManager,
    _distance,
    _choose_movement
)

# Use the exact same evaluation harness as J1/J2
from run_scalability import ScalabilityCoordinator, count_actions

SEEDS = [42, 43, 44, 45, 46]
TARGET_MELONS = 12

class CompactV1Manager(HybridWorkerManager):
    """
    Overrides Priority 4 (PLANT) to cluster plants around the shed
    instead of wandering and scattering them.
    """
    def execute(self, state, context):
        my_farm = state.my_farm
        all_units = [my_farm.farmer] + list(my_farm.hands)
        
        unwatered_tiles = []
        harvestable_tiles = []
        empty_tiles = []
        weed_tiles = []
        
        max_melon_day = CROP_DATA["MELON"]["max_yield_day"]
        max_carrot_day = CROP_DATA["CARROT"]["max_yield_day"]
        
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                pos = Position(x=x, y=y)
                if tile.kind == "PLANT":
                    max_day = max_melon_day if tile.crop == "MELON" else max_carrot_day
                    if tile.planted_day is not None and (state.day - tile.planted_day) >= max_day:
                        harvestable_tiles.append(pos)
                    elif not tile.watered_today:
                        unwatered_tiles.append(pos)
                elif tile.kind == "WEED":
                    weed_tiles.append(pos)
                elif tile.is_empty():
                    empty_tiles.append(pos)
                    
        shed_tiles = [Position(x=x, y=y) for x, y in SHED_ADJACENT_TILES]
        targeted_tiles = set()
        unit_actions = []
        
        seed_reserves = {}
        
        for unit in all_units:
            # Priority 1: WATER (Closest to worker)
            valid_water = [p for p in unwatered_tiles if p not in targeted_tiles]
            if valid_water:
                target = min(valid_water, key=lambda p: _distance(unit.position, p))
                targeted_tiles.add(target)
                if unit.position == target:
                    action = ["WATER"]
                else:
                    action = [_choose_movement(unit.position, target)]
                unit_actions.append(action)
                continue
                
            # Priority 2: HARVEST (Closest to worker)
            valid_harvest = [p for p in harvestable_tiles if p not in targeted_tiles]
            if valid_harvest:
                target = min(valid_harvest, key=lambda p: _distance(unit.position, p))
                targeted_tiles.add(target)
                if unit.position == target:
                    action = ["HARVEST"]
                else:
                    action = [_choose_movement(unit.position, target)]
                unit_actions.append(action)
                continue
                
            # Priority 3: DROP (Closest shed)
            has_produce = any(count > 0 for item, count in unit.inventory.items.items() if item != "FERTILIZER")
            if has_produce:
                target = min(shed_tiles, key=lambda p: _distance(unit.position, p))
                if unit.position in shed_tiles:
                    action = ["DROP"]
                else:
                    action = [_choose_movement(unit.position, target)]
                unit_actions.append(action)
                continue
                
            # Priority 4: PLANT (Closest to SHED instead of closest to worker)
            valid_empty = [p for p in empty_tiles if p not in targeted_tiles]
            if valid_empty:
                best_seed_crop = "MELON"
                if my_farm.seeds and my_farm.seeds.get(best_seed_crop, 0) > seed_reserves.get(best_seed_crop, 0):
                    # J3 HEURISTIC: Compact Production Cluster
                    # Find the tile that minimizes distance to the closest shed drop-off point
                    target = min(valid_empty, key=lambda p: min(_distance(p, s) for s in shed_tiles))
                    targeted_tiles.add(target)
                    seed_reserves[best_seed_crop] = seed_reserves.get(best_seed_crop, 0) + 1
                    if unit.position == target:
                        action = ["PLANT", best_seed_crop]
                    else:
                        action = [_choose_movement(unit.position, target)]
                    unit_actions.append(action)
                    continue
                
            unit_actions.append(["PASS"])
            
        return {
            "farmer": unit_actions[0],
            "hands": unit_actions[1:]
        }


def run_episode(scheduler_cls, fixed_workers: int, seed: int):
    # exact copy of J1 harness but we also measure weed interference, dist, etc.
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    trainer = env.train([None, "random"])
    agent = ScalabilityCoordinator(scheduler_cls, fixed_workers)

    obs = trainer.reset()
    total_productive = 0
    total_movement = 0
    total_pass = 0
    total_steps = 0
    
    act_counts = {"WATER": 0, "PLANT": 0, "HARVEST": 0}
    
    # Calculate average distance traveled by worker per productive action
    # We can approximate this by (total_movement / total_productive)
    
    while not env.done:
        try:
            action = agent(obs)
        except ValueError as e:
            if "out of range" in str(e):
                break
            raise

        p, m, ps = count_actions(action)
        total_productive += p
        total_movement += m
        total_pass += ps
        total_steps += 1
        
        all_ua = [action.get("farmer", ["PASS"])] + action.get("hands", [])
        for ua in all_ua:
            if ua and ua[0] in act_counts:
                act_counts[ua[0]] += 1

        obs, reward, done, info = trainer.step(action)

    farm = obs["farms"][0] if isinstance(obs, dict) else obs.farms[0]
    final_cash = farm.get("money", 0) if isinstance(farm, dict) else farm.money
    
    final_weeds = 0
    tiles = farm.get("tiles", []) if isinstance(farm, dict) else farm.tiles
    for row in tiles:
        for t in row:
            if isinstance(t, dict):
                if t.get('kind') == 'WEED': final_weeds += 1
            elif hasattr(t, "kind"):
                if t.kind == 'WEED': final_weeds += 1
            elif isinstance(t, str):
                if t == 'WEED': final_weeds += 1

    return {
        "final_cash": final_cash,
        "productive": total_productive,
        "movement": total_movement,
        "passes": total_pass,
        "act_counts": act_counts,
        "final_weeds": final_weeds
    }

def evaluate(scheduler_cls, scheduler_name: str, fixed_workers: int, seeds):
    results = [run_episode(scheduler_cls, fixed_workers, s) for s in seeds]
    rewards = [r["final_cash"] for r in results]
    unit_count = fixed_workers + 1

    mean_r = statistics.mean(rewards)
    mean_prod = statistics.mean(r["productive"] for r in results)
    mean_move = statistics.mean(r["movement"] for r in results)
    mean_pass = statistics.mean(r["passes"] for r in results)
    
    mean_water = statistics.mean(r["act_counts"]["WATER"] for r in results)
    mean_plant = statistics.mean(r["act_counts"]["PLANT"] for r in results)
    mean_harvest = statistics.mean(r["act_counts"]["HARVEST"] for r in results)
    mean_weeds = statistics.mean(r["final_weeds"] for r in results)

    return {
        "scheduler": scheduler_name,
        "mean_reward": mean_r,
        "productive": mean_prod,
        "movement": mean_move,
        "passes": mean_pass,
        "water": mean_water,
        "plant": mean_plant,
        "harvest": mean_harvest,
        "weeds": mean_weeds,
        "worker_utilization": (mean_prod + mean_move) / (mean_prod + mean_move + mean_pass),
        "dist_per_prod": mean_move / mean_prod if mean_prod > 0 else 0
    }

def main():
    print("="*60)
    print("J3 — SPATIAL LOCALITY (Fixed 2 Workers, 12 Melons)")
    print("="*60)
    
    print("Evaluating A: Scattered Production (Control / HybridWorkerManager)")
    res_A = evaluate(HybridWorkerManager, "A_Scattered", 2, SEEDS)
    
    print("Evaluating B: Compact Production Cluster (CompactV1Manager)")
    res_B = evaluate(CompactV1Manager, "B_Compact", 2, SEEDS)
    
    report = f"""# Experiment J3 — Spatial Locality Report

| Metric | A (Scattered) | B (Compact Cluster) | Delta |
|--------|---------------|---------------------|-------|
| **Mean Reward** | ${res_A['mean_reward']:.0f} | ${res_B['mean_reward']:.0f} | {res_B['mean_reward'] - res_A['mean_reward']:+.0f} |
| **Productive Actions** | {res_A['productive']:.1f} | {res_B['productive']:.1f} | {res_B['productive'] - res_A['productive']:+.1f} |
| **Movement Actions** | {res_A['movement']:.1f} | {res_B['movement']:.1f} | {res_B['movement'] - res_A['movement']:+.1f} |
| **PASS (Idle/Stuck)** | {res_A['passes']:.1f} | {res_B['passes']:.1f} | {res_B['passes'] - res_A['passes']:+.1f} |
| **WATER Actions** | {res_A['water']:.1f} | {res_B['water']:.1f} | {res_B['water'] - res_A['water']:+.1f} |
| **PLANT Actions** | {res_A['plant']:.1f} | {res_B['plant']:.1f} | {res_B['plant'] - res_A['plant']:+.1f} |
| **HARVEST Actions** | {res_A['harvest']:.1f} | {res_B['harvest']:.1f} | {res_B['harvest'] - res_A['harvest']:+.1f} |
| **Worker Utilization** | {res_A['worker_utilization']*100:.1f}% | {res_B['worker_utilization']*100:.1f}% | {(res_B['worker_utilization'] - res_A['worker_utilization'])*100:+.1f}% |
| **Movements per Prod.** | {res_A['dist_per_prod']:.2f} | {res_B['dist_per_prod']:.2f} | {res_B['dist_per_prod'] - res_A['dist_per_prod']:+.2f} |
| **Final Weeds** | {res_A['weeds']:.1f} | {res_B['weeds']:.1f} | {res_B['weeds'] - res_A['weeds']:+.1f} |

"""
    with open("j3_report.md", "w") as f:
        f.write(report)
        
    print(report)

if __name__ == "__main__":
    main()
