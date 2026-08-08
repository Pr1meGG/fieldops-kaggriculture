"""
Experiment K2 — Livestock Workload
==================================
Test whether adding 1 Cow and 1 Sheep (the opponent's Day 0 purchase)
generates positive marginal value for a second worker, keeping the 
crop footprint fixed at 12 Melons.
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
from run_scalability import ScalabilityCoordinator

SEEDS = [42, 43, 44, 45, 46]

class BaseMetricsManager(HybridWorkerManager):
    """Telemetry for K2 metrics."""
    def __init__(self):
        self.metrics = {
            "productive": 0,
            "movement": 0,
            "passes": 0,
            "act_counts": {"WATER": 0, "PLANT": 0, "HARVEST": 0, "DROP": 0, "FEED": 0, "CARE": 0, "COLLECT_FERTILIZER": 0, "BUILD_PASTURE": 0, "PICKUP": 0, "PLACE": 0, "SELL": 0},
            "feed_cost": 0,
            "animal_cost": 0
        }
    def record_action(self, action_type):
        if action_type in ["WATER", "HARVEST", "PLANT", "DROP", "DIG", "FEED", "CARE", "COLLECT_FERTILIZER", "BUILD_PASTURE", "PICKUP", "PLACE"]:
            self.metrics["productive"] += 1
            self.metrics["act_counts"][action_type] += 1
        elif action_type in ["NORTH", "SOUTH", "EAST", "WEST"]:
            self.metrics["movement"] += 1
        else:
            self.metrics["passes"] += 1

class PolicyB_LocalFirstLivestock(BaseMetricsManager):
    """Local-First task assignment extended with Livestock and Pasture building."""
    def __init__(self, target_cows=0, target_sheep=0):
        super().__init__()
        self.target_cows = target_cows
        self.target_sheep = target_sheep

    def execute(self, state, context):
        my_farm = state.my_farm
        all_units = [my_farm.farmer] + list(my_farm.hands)
        
        # Analyze tiles
        unwatered, harvestable, empty = [], [], []
        hungry, needs_care, has_fert = [], [], []
        pastures = []
        
        max_melon_day = CROP_DATA["MELON"]["max_yield_day"]
        
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                pos = Position(x=x, y=y)
                if tile.kind == "PLANT":
                    if tile.planted_day is not None and (state.day - tile.planted_day) >= max_melon_day:
                        harvestable.append(pos)
                    elif not tile.watered_today:
                        unwatered.append(pos)
                elif tile.is_empty():
                    empty.append(pos)
                elif tile.kind == "PASTURE":
                    pastures.append(pos)
                    if tile.has_animal():
                        if not tile.fed_today:
                            hungry.append(pos)
                        if not tile.cared_today:
                            needs_care.append(pos)
                        if tile.fertilizer_available:
                            has_fert.append(pos)
                    
        shed_tiles = [Position(x=x, y=y) for x, y in SHED_ADJACENT_TILES]
        targeted_tiles = set()
        unit_actions = []
        seed_reserves = 0
        wheat_reserves = 0
        
        # Determine if we need to build pastures
        needed_pastures = (self.target_cows + self.target_sheep) - len(pastures)
        pastures_to_build = []
        if needed_pastures > 0:
            # Reserve empty tiles furthest from shed for pastures (so crops stay near shed)
            sorted_empty = sorted(empty, key=lambda p: min(_distance(p, s) for s in shed_tiles), reverse=True)
            pastures_to_build = sorted_empty[:needed_pastures]
        
        for unit in all_units:
            has_produce = any(c > 0 for i, c in unit.inventory.items.items() if i not in ("FERTILIZER", "WHEAT", "COW", "SHEEP"))
            has_fert_inv = unit.inventory.items.get("FERTILIZER", 0) > 0
            carrying_cow = unit.inventory.items.get("COW", 0) > 0
            carrying_sheep = unit.inventory.items.get("SHEEP", 0) > 0
            carrying_wheat = unit.inventory.items.get("WHEAT", 0) > 0
            
            unplaced_cows = my_farm.shed.items.get("COW", 0)
            unplaced_sheep = my_farm.shed.items.get("SHEEP", 0)
            
            empty_pastures = [p for p in pastures if not my_farm.tiles[p.y][p.x].has_animal()]
            avail_empty_pastures = [p for p in empty_pastures if p not in targeted_tiles]
            
            avail_seeds = my_farm.seeds.get("MELON", 0) if my_farm.seeds else 0
            can_plant = avail_seeds > seed_reserves
            
            avail_wheat = my_farm.shed.items.get("WHEAT", 0) + unit.inventory.items.get("WHEAT", 0)
            can_feed = avail_wheat > wheat_reserves
            
            tasks = []
            
            # Animal Delivery
            if carrying_cow or carrying_sheep:
                animal = "COW" if carrying_cow else "SHEEP"
                if avail_empty_pastures:
                    tasks.append((avail_empty_pastures[0], f"PLACE_{animal}", 1000))
            else:
                if avail_empty_pastures:
                    # Only pickup if we aren't already targeting the shed for pickup by another worker
                    pickup_targeted = any(t == shed_tiles[0] and t_type.startswith("PICKUP_") for t, t_type, _ in tasks) # Wait, this worker's tasks. 
                    # Instead of cross-worker, just let priority handle it, or use targeted_tiles for shed_tiles[0].
                    if unplaced_cows > 0: tasks.append((shed_tiles[0], "PICKUP_COW", 900))
                    elif unplaced_sheep > 0: tasks.append((shed_tiles[0], "PICKUP_SHEEP", 900))
            
            # Highest priority: FEED (Priority 110 or 1000 if carrying)
            if hungry:
                if carrying_wheat:
                    for p in hungry:
                        if p not in targeted_tiles: tasks.append((p, "FEED", 1000))
                else:
                    avail_wheat = my_farm.shed.items.get("WHEAT", 0)
                    if avail_wheat > wheat_reserves:
                        # Only pickup if we aren't already targeting the shed
                        tasks.append((shed_tiles[0], "PICKUP_WHEAT", 900))
                    
            # High priority: WATER (100), CARE (95)
            for p in unwatered:
                if p not in targeted_tiles: tasks.append((p, "WATER", 100))
            for p in needs_care:
                if p not in targeted_tiles: tasks.append((p, "CARE", 95))
                
            # Medium priority: HARVEST (90), COLLECT_FERTILIZER (85), BUILD_PASTURE (85)
            for p in harvestable:
                if p not in targeted_tiles: tasks.append((p, "HARVEST", 90))
                
            has_animal_harvest = [
                Position(x=x, y=y) for y, row in enumerate(my_farm.tiles) for x, t in enumerate(row)
                if t.is_animal() and t.yield_units and t.yield_units > 0
            ]
            for p in has_animal_harvest:
                if p not in targeted_tiles: tasks.append((p, "HARVEST", 90))
                
            has_fertilizer = [
                Position(x=x, y=y) for y, row in enumerate(my_farm.tiles) for x, t in enumerate(row)
                if t.is_animal() and getattr(t, 'fertilizer_available', False)
            ]
            for p in has_fertilizer:
                if p not in targeted_tiles: tasks.append((p, "COLLECT_FERTILIZER", 85))
            for p in has_fert:
                if p not in targeted_tiles: tasks.append((p, "COLLECT_FERTILIZER", 85))
            for p in pastures_to_build:
                if p not in targeted_tiles: tasks.append((p, "BUILD_PASTURE", 85))
                
            # Lower priority: DROP (80)
            if has_produce or has_fert_inv:
                for p in shed_tiles: tasks.append((p, "DROP", 80))
                
            # Lowest priority: PLANT (50)
            if can_plant:
                for p in empty:
                    if p not in targeted_tiles and p not in pastures_to_build: 
                        tasks.append((p, "PLANT", 50))
                    
            target = None
            action = ["PASS"]
            
            if tasks:
                tasks_with_dist = [(p, t_type, prio, _distance(unit.position, p)) for p, t_type, prio in tasks]
                local_tasks = [t for t in tasks_with_dist if t[3] <= 3]
                
                # If there's an ultra-high priority delivery task (>=900), it MUST bypass local preference
                high_prio_tasks = [t for t in tasks_with_dist if t[2] >= 900]
                
                if high_prio_tasks:
                    best = min(high_prio_tasks, key=lambda x: (-x[2], x[3]))
                elif local_tasks:
                    best = min(local_tasks, key=lambda x: (-x[2], x[3]))
                else:
                    best = min(tasks_with_dist, key=lambda x: (-x[2], x[3]))
                    
                target = best[0]
                t_type = best[1]
                
                if t_type != "DROP":
                    targeted_tiles.add(target)
                if t_type == "PLANT":
                    seed_reserves += 1
                if t_type == "FEED":
                    wheat_reserves += 1
                    
                if unit.position == target:
                    if t_type == "PLANT":
                        action = ["PLANT", "MELON"]
                    elif t_type == "DROP":
                        action = ["DROP"]
                    elif t_type.startswith("PLACE_"):
                        action = ["PLACE", t_type.split("_")[1]]
                    elif t_type.startswith("PICKUP_"):
                        action = ["PICKUP", t_type.split("_")[1]]
                    else:
                        action = [t_type]
                else:
                    action = [_choose_movement(unit.position, target)]
                    
            self.record_action(action[0])
            unit_actions.append(action)

        return {"farmer": unit_actions[0], "hands": unit_actions[1:]}


class K2Coordinator(ScalabilityCoordinator):
    def __init__(self, scheduler_cls, fixed_workers: int, target_cows: int, target_sheep: int):
        super().__init__(scheduler_cls, fixed_workers)
        self.scheduler = scheduler_cls(target_cows, target_sheep)
        self.managers = [self.scheduler]
        self.target_cows = target_cows
        self.target_sheep = target_sheep
        self.target_melons = 12
        
        self.sold_melons = 0
        self.sold_milk = 0
        self.sold_wool = 0
        self.sold_fert = 0
        
        self.wheat_bought = 0
        self.cows_bought = 0
        self.sheep_bought = 0

    def __call__(self, obs):
        state = ObservationParser.parse(obs)
        my_farm = state.my_farm
        
        actions = super().__call__(obs) # Get base actions
        
        # We need to manually handle market actions for this experiment.
        # Preserve HIRE actions, but clear SELL and BUY_SEED
        actions["market"] = [a for a in actions["market"] if a[0] not in ("SELL", "BUY_SEED")]
        
        # Count animals currently owned
        owned_cows = my_farm.shed.items.get("COW", 0) + sum(1 for row in my_farm.tiles for t in row if t.is_animal() and t.animal == "COW")
        owned_sheep = my_farm.shed.items.get("SHEEP", 0) + sum(1 for row in my_farm.tiles for t in row if t.is_animal() and t.animal == "SHEEP")
        
        # Ensure we have enough pastures BEFORE buying animals
        pastures = sum(1 for row in my_farm.tiles for t in row if t.kind == "PASTURE")
        animals_to_buy = []
        if owned_cows < self.target_cows and pastures > (owned_cows + owned_sheep):
            animals_to_buy.append(("COW", self.target_cows - owned_cows, 1000))
        elif owned_sheep < self.target_sheep and pastures > (owned_cows + owned_sheep):
            animals_to_buy.append(("SHEEP", self.target_sheep - owned_sheep, 1000))
            
        money = my_farm.money
        
        for anim, count, cost in animals_to_buy:
            if money >= count * cost:
                actions["market"].append(["BUY_ANIMAL", anim, count])
                money -= count * cost
                if anim == "COW": self.cows_bought += count
                else: self.sheep_bought += count
                
        # Buy Seeds (12 Melons target)
        current_plants = sum(1 for row in my_farm.tiles for t in row if t.is_plant())
        seeds_held = my_farm.seeds.get("MELON", 0) if my_farm.seeds else 0
        need_seeds = self.target_melons - seeds_held - current_plants
        if need_seeds > 0 and money >= need_seeds * 10:
            actions["market"].append(["BUY_SEED", "MELON", need_seeds])
            money -= need_seeds * 10
            
        # Buy Wheat for feed (Maintain 10 wheat buffer per animal owned)
        total_animals = owned_cows + owned_sheep
        wheat_held = my_farm.shed.items.get("WHEAT", 0)
        for u in [my_farm.farmer] + list(my_farm.hands):
            wheat_held += u.inventory.items.get("WHEAT", 0)
            
        if total_animals > 0 and wheat_held < total_animals * 10:
            need_wheat = (total_animals * 10) - wheat_held
            if money >= need_wheat * 25: # wheat costs ~$25
                actions["market"].append(["BUY_PRODUCT", "WHEAT", need_wheat])
                money -= need_wheat * 25
                self.wheat_bought += need_wheat
                self.scheduler.metrics["feed_cost"] += need_wheat * 25

        # Sell products
        to_sell = ["MELON", "MILK", "WOOL", "FERTILIZER"]
        for prod in to_sell:
            amt = my_farm.shed.items.get(prod, 0)
            if amt > 0:
                actions["market"].append(["SELL", prod, amt])
                self.scheduler.metrics["act_counts"]["SELL"] += 1
                if prod == "MELON": self.sold_melons += amt
                elif prod == "MILK": self.sold_milk += amt
                elif prod == "WOOL": self.sold_wool += amt
                elif prod == "FERTILIZER": self.sold_fert += amt

        return actions

def run_episode(config_name: str, workers: int, cows: int, sheep: int, seed: int):
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    trainer = env.train([None, "random"])
    
    agent = K2Coordinator(PolicyB_LocalFirstLivestock, workers, cows, sheep)
    obs = trainer.reset()
    
    while not env.done:
        try:
            action = agent(obs)
            obs, reward, done, info = trainer.step(action)
        except ValueError as e:
            if "out of range" in str(e): break
            raise
            
    farm = obs["farms"][0] if isinstance(obs, dict) else obs.farms[0]
    final_cash = farm.get("money", 0) if isinstance(farm, dict) else farm.money
    
    return {
        "config": config_name,
        "final_cash": final_cash,
        "sold_melons": agent.sold_melons,
        "sold_milk": agent.sold_milk,
        "sold_wool": agent.sold_wool,
        "sold_fert": agent.sold_fert,
        "feed_bought": agent.wheat_bought,
        "metrics": agent.scheduler.metrics
    }

def evaluate(config_name: str, workers: int, cows: int, sheep: int):
    results = [run_episode(config_name, workers, cows, sheep, s) for s in SEEDS]
    mean_r = statistics.mean(r["final_cash"] for r in results)
    
    # Aggregated metrics
    mean_prod = statistics.mean(r["metrics"]["productive"] for r in results)
    mean_move = statistics.mean(r["metrics"]["movement"] for r in results)
    mean_pass = statistics.mean(r["metrics"]["passes"] for r in results)
    
    total_actions = mean_prod + mean_move + mean_pass
    utilization = (mean_prod + mean_move) / total_actions if total_actions > 0 else 0
    
    return {
        "config": config_name,
        "workers": workers,
        "cows": cows,
        "sheep": sheep,
        "mean_reward": mean_r,
        "productive": mean_prod,
        "movement": mean_move,
        "utilization": utilization,
        "sold_melons": statistics.mean(r["sold_melons"] for r in results),
        "sold_milk": statistics.mean(r["sold_milk"] for r in results),
        "sold_wool": statistics.mean(r["sold_wool"] for r in results),
        "sold_fert": statistics.mean(r["sold_fert"] for r in results),
        "feed_bought": statistics.mean(r["feed_bought"] for r in results),
        "acts": {
            k: statistics.mean(r["metrics"]["act_counts"][k] for r in results)
            for k in results[0]["metrics"]["act_counts"]
        }
    }

def main():
    configs = [
        ("A (1W, No Live)", 1, 0, 0),
        ("B (1W, 1C+1S)", 1, 1, 1),
        ("C (2W, 1C+1S)", 2, 1, 1)
    ]
    
    all_results = []
    
    print("Running K2 Experiment...")
    for name, w, c, s in configs:
        print(f"Evaluating {name}...")
        res = evaluate(name, w, c, s)
        all_results.append(res)
        print(f"  Result: ${res['mean_reward']:.0f}")
        
    report = "# Experiment K2 — Livestock Workload Report\n\n"
    report += "| Config | Workers | Livestock | Mean Reward | Delta vs Control | Util% | Prod | Move | Melons | Milk | Wool | Fert | Feed Buy | \n"
    report += "|--------|---------|-----------|-------------|------------------|-------|------|------|--------|------|------|------|----------| \n"
    
    control_reward = all_results[0]['mean_reward']
    for r in all_results:
        ls_str = f"{r['cows']}C+{r['sheep']}S"
        delta = r['mean_reward'] - control_reward
        delta_str = f"{delta:+.0f}" if r != all_results[0] else "—"
        
        report += f"| {r['config']} | {r['workers']} | {ls_str} | ${r['mean_reward']:.0f} | {delta_str} | {r['utilization']*100:.1f}% | {r['productive']:.1f} | {r['movement']:.1f} | {r['sold_melons']:.1f} | {r['sold_milk']:.1f} | {r['sold_wool']:.1f} | {r['sold_fert']:.1f} | {r['feed_bought']:.1f} |\n"
        
    with open("k2_report.md", "w") as f:
        f.write(report)
        
    print("\nResults saved to k2_report.md")

if __name__ == "__main__":
    main()
