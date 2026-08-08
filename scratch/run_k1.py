"""
Experiment K1 — Production Scale
================================
Test if increased crop workload allows the Local-First scheduler
to generate positive marginal value from additional workers.
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
    """Telemetry for metrics."""
    def __init__(self):
        self.metrics = {
            "productive": 0,
            "movement": 0,
            "passes": 0,
            "act_counts": {"WATER": 0, "PLANT": 0, "HARVEST": 0, "DROP": 0, "DIG": 0}
        }
    def record_action(self, action_type):
        if action_type in ["WATER", "HARVEST", "PLANT", "DROP", "DIG"]:
            self.metrics["productive"] += 1
            self.metrics["act_counts"][action_type] += 1
        elif action_type in ["NORTH", "SOUTH", "EAST", "WEST"]:
            self.metrics["movement"] += 1
        else:
            self.metrics["passes"] += 1

class PolicyB_LocalFirst(BaseMetricsManager):
    """Local-First task assignment."""
    def execute(self, state, context):
        my_farm = state.my_farm
        all_units = [my_farm.farmer] + list(my_farm.hands)
        
        unwatered, harvestable, empty = [], [], []
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
                    
        shed_tiles = [Position(x=x, y=y) for x, y in SHED_ADJACENT_TILES]
        targeted_tiles = set()
        unit_actions = []
        seed_reserves = 0
        
        for unit in all_units:
            has_produce = any(c > 0 for i, c in unit.inventory.items.items() if i != "FERTILIZER")
            avail_seeds = my_farm.seeds.get("MELON", 0) if my_farm.seeds else 0
            can_plant = avail_seeds > seed_reserves
            
            tasks = []
            for p in unwatered:
                if p not in targeted_tiles: tasks.append((p, "WATER", 100))
            for p in harvestable:
                if p not in targeted_tiles: tasks.append((p, "HARVEST", 90))
            if has_produce:
                for p in shed_tiles: tasks.append((p, "DROP", 80))
            if can_plant:
                for p in empty:
                    if p not in targeted_tiles: tasks.append((p, "PLANT", 50))
                    
            target = None
            action = ["PASS"]
            
            if tasks:
                tasks_with_dist = [(p, t_type, prio, _distance(unit.position, p)) for p, t_type, prio in tasks]
                local_tasks = [t for t in tasks_with_dist if t[3] <= 3]
                
                if local_tasks:
                    best = min(local_tasks, key=lambda x: (-x[2], x[3]))
                else:
                    best = min(tasks_with_dist, key=lambda x: (-x[2], x[3]))
                    
                target = best[0]
                t_type = best[1]
                
                if t_type != "DROP":
                    targeted_tiles.add(target)
                if t_type == "PLANT":
                    seed_reserves += 1
                    
                if unit.position == target:
                    action = [t_type] if t_type != "PLANT" else ["PLANT", "MELON"]
                else:
                    action = [_choose_movement(unit.position, target)]
                    
            self.record_action(action[0])
            unit_actions.append(action)

        return {"farmer": unit_actions[0], "hands": unit_actions[1:]}

# Customized Coordinator to dynamically set TARGET_MELONS
class K1Coordinator(ScalabilityCoordinator):
    def __init__(self, scheduler_cls, fixed_workers: int, target_melons: int):
        super().__init__(scheduler_cls, fixed_workers)
        self.target_melons = target_melons
        self.sold_melons = 0

    def __call__(self, obs):
        actions = super().__call__(obs)
        state = ObservationParser.parse(obs)
        my_farm = state.my_farm
        
        # Override seed buying with the specific target_melons for this test
        # (super() already buys seeds, but uses a global TARGET_MELONS. We'll overwrite that logic)
        current_plants = sum(1 for row in my_farm.tiles for t in row if t.is_plant())
        seeds_held = my_farm.seeds.get("MELON", 0) if my_farm.seeds else 0
        need_seeds = self.target_melons - seeds_held - current_plants
        
        # Strip out old seed buy actions (from super)
        actions["market"] = [a for a in actions["market"] if a[0] != "BUY_SEED"]
        
        if need_seeds > 0 and my_farm.money >= need_seeds * 10:
            actions["market"].append(["BUY_SEED", "MELON", need_seeds])
            
        # Count sales
        for a in actions["market"]:
            if a[0] == "SELL" and len(a) > 2 and a[1] == "MELON":
                self.sold_melons += a[2]

        return actions

def run_episode(workers: int, melons: int, seed: int):
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    trainer = env.train([None, "random"])
    
    agent = K1Coordinator(PolicyB_LocalFirst, workers, melons)
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
    manager = agent.scheduler
    
    # Check final weeds
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
        "metrics": manager.metrics,
        "sold_melons": agent.sold_melons,
        "weeds": final_weeds
    }

def evaluate(workers: int, melons: int):
    results = [run_episode(workers, melons, s) for s in SEEDS]
    rewards = [r["final_cash"] for r in results]
    mean_r = statistics.mean(rewards)
    
    mean_prod = statistics.mean(r["metrics"]["productive"] for r in results)
    mean_move = statistics.mean(r["metrics"]["movement"] for r in results)
    mean_pass = statistics.mean(r["metrics"]["passes"] for r in results)
    mean_sold = statistics.mean(r["sold_melons"] for r in results)
    mean_weeds = statistics.mean(r["weeds"] for r in results)
    
    w_acts = {"WATER": 0, "PLANT": 0, "HARVEST": 0, "DROP": 0}
    for k in w_acts:
        w_acts[k] = statistics.mean(r["metrics"]["act_counts"][k] for r in results)
        
    total_actions = mean_prod + mean_move + mean_pass
    utilization = (mean_prod + mean_move) / total_actions if total_actions > 0 else 0
    
    # +1 because farmer is always 1 worker
    total_labor = workers + 1
    
    return {
        "melons": melons,
        "workers": workers,
        "mean_reward": mean_r,
        "productive": mean_prod,
        "movement": mean_move,
        "passes": mean_pass,
        "utilization": utilization,
        "sold": mean_sold,
        "weeds": mean_weeds,
        "w_acts": w_acts,
        "reward_per_worker": mean_r / total_labor
    }

def main():
    target_melons = [12, 16, 20, 25]
    worker_counts = [1, 2, 3]
    
    all_results = []
    
    for melons in target_melons:
        print(f"\n--- {melons} Melons ---")
        prev_reward = None
        for w in worker_counts:
            print(f"  {w} workers...", end=" ", flush=True)
            res = evaluate(w, melons)
            all_results.append(res)
            
            marginal = ""
            if prev_reward is not None:
                marginal = f"(Marginal: {res['mean_reward'] - prev_reward:+.0f})"
            print(f"${res['mean_reward']:.0f} {marginal}")
            prev_reward = res['mean_reward']
            
    # Build report
    report = "# Experiment K1 — Production Scale Report\n\n"
    report += "| Melons | Workers | Reward | Marginal $ | Sold | Prod | Move | Util% | Weeds | $ / Worker |\n"
    report += "|--------|---------|--------|------------|------|------|------|-------|-------|------------|\n"
    
    prev_by_melon = {}
    for r in all_results:
        melons = r['melons']
        prev_r = prev_by_melon.get(melons)
        marginal_str = "—"
        if prev_r is not None:
            marginal_str = f"{r['mean_reward'] - prev_r:+.0f}"
            
        report += f"| {r['melons']} | {r['workers']} | ${r['mean_reward']:.0f} | {marginal_str} | {r['sold']:.1f} | {r['productive']:.1f} | {r['movement']:.1f} | {r['utilization']*100:.1f}% | {r['weeds']:.1f} | ${r['reward_per_worker']:.0f} |\n"
        prev_by_melon[melons] = r['mean_reward']
        
    with open("k1_report.md", "w") as f:
        f.write(report)
        
    print("\nResults saved to k1_report.md")
    
if __name__ == "__main__":
    main()
