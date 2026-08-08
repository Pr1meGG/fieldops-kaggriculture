"""
Experiment J4 — Worker Locality & Task Ownership
================================================
Test whether local-first and adaptive scoring can make 
additional workers productive compared to global V1.
"""

import os
import sys
import statistics
import json
from collections import defaultdict

sys.path.insert(0, os.path.abspath("src"))

from kaggle_environments import make
from fieldops.state import ObservationParser, Position
from fieldops.constants import CROP_DATA, SHED_ADJACENT_TILES
from fieldops.managers.worker_manager import (
    WorkerManager,
    HybridWorkerManager,
    _distance,
    _choose_movement
)

from run_scalability import ScalabilityCoordinator

SEEDS = [42, 43, 44, 45, 46]
TARGET_MELONS = 12


class BaseMetricsManager(HybridWorkerManager):
    """Adds telemetry for J4 metrics."""
    def __init__(self):
        self.j4_metrics = {
            "target_conflicts": 0,
            "task_switches": 0,
            "productive": 0,
            "movement": 0,
            "passes": 0,
            "act_counts": {"WATER": 0, "PLANT": 0, "HARVEST": 0, "DROP": 0, "DIG": 0}
        }
        self.last_targets = {}

    def record_action(self, unit_id, target_pos, action_type):
        if action_type in ["WATER", "HARVEST", "PLANT", "DROP", "DIG"]:
            self.j4_metrics["productive"] += 1
            self.j4_metrics["act_counts"][action_type] += 1
        elif action_type in ["NORTH", "SOUTH", "EAST", "WEST"]:
            self.j4_metrics["movement"] += 1
        else:
            self.j4_metrics["passes"] += 1

        if target_pos:
            prev_target = self.last_targets.get(unit_id)
            if prev_target and prev_target != target_pos:
                # If they were moving towards A, and now moving towards B
                self.j4_metrics["task_switches"] += 1
            self.last_targets[unit_id] = target_pos
        else:
            self.last_targets[unit_id] = None


class PolicyA_GlobalV1(BaseMetricsManager):
    """Control: V1 Unit-Centric (Scattered). Exactly matches HybridWorkerManager but tracks metrics."""
    def execute(self, state, context):
        my_farm = state.my_farm
        all_units = [my_farm.farmer] + list(my_farm.hands)
        
        # Collect tasks
        unwatered, harvestable, empty, weed = [], [], [], []
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
        
        for i, unit in enumerate(all_units):
            uid = id(unit)
            action = ["PASS"]
            target = None
            
            # P1: WATER
            v_water = [p for p in unwatered if p not in targeted_tiles]
            if v_water:
                target = min(v_water, key=lambda p: _distance(unit.position, p))
                targeted_tiles.add(target)
                action = ["WATER"] if unit.position == target else [_choose_movement(unit.position, target)]
            # P2: HARVEST
            elif [p for p in harvestable if p not in targeted_tiles]:
                v_harv = [p for p in harvestable if p not in targeted_tiles]
                target = min(v_harv, key=lambda p: _distance(unit.position, p))
                targeted_tiles.add(target)
                action = ["HARVEST"] if unit.position == target else [_choose_movement(unit.position, target)]
            # P3: DROP
            elif any(c > 0 for i, c in unit.inventory.items.items() if i != "FERTILIZER"):
                target = min(shed_tiles, key=lambda p: _distance(unit.position, p))
                action = ["DROP"] if unit.position in shed_tiles else [_choose_movement(unit.position, target)]
            # P4: PLANT
            elif [p for p in empty if p not in targeted_tiles]:
                v_empty = [p for p in empty if p not in targeted_tiles]
                avail_seeds = my_farm.seeds.get("MELON", 0) if my_farm.seeds else 0
                if avail_seeds > seed_reserves:
                    target = min(v_empty, key=lambda p: _distance(unit.position, p))
                    targeted_tiles.add(target)
                    seed_reserves += 1
                    action = ["PLANT", "MELON"] if unit.position == target else [_choose_movement(unit.position, target)]
            
            self.record_action(uid, target, action[0])
            unit_actions.append(action)
            
        # Target conflicts check (did multiple units target the exact same tile?)
        all_targets = [self.last_targets.get(id(u)) for u in all_units if self.last_targets.get(id(u))]
        conflicts = len(all_targets) - len(set(all_targets))
        if conflicts > 0:
            self.j4_metrics["target_conflicts"] += conflicts

        return {"farmer": unit_actions[0], "hands": unit_actions[1:]}


class PolicyB_LocalFirst(BaseMetricsManager):
    """
    Evaluates ALL valid tasks (across priorities). 
    If a task is <= radius, pick highest priority local task. 
    Else pick highest priority global task.
    """
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
            uid = id(unit)
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
                # Add distance to tasks
                tasks_with_dist = [(p, t_type, prio, _distance(unit.position, p)) for p, t_type, prio in tasks]
                
                local_tasks = [t for t in tasks_with_dist if t[3] <= 3]
                if local_tasks:
                    # Sort by Priority DESC, then Distance ASC
                    best = min(local_tasks, key=lambda x: (-x[2], x[3]))
                else:
                    # Fallback global
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
                    
            self.record_action(uid, target, action[0])
            unit_actions.append(action)

        all_targets = [self.last_targets.get(id(u)) for u in all_units if self.last_targets.get(id(u))]
        conflicts = len(all_targets) - len(set(all_targets))
        if conflicts > 0:
            self.j4_metrics["target_conflicts"] += conflicts

        return {"farmer": unit_actions[0], "hands": unit_actions[1:]}


class PolicyC_Adaptive(BaseMetricsManager):
    """
    Explicit scoring function:
    task_priority + locality_benefit - travel_cost - interference_risk
    """
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
            uid = id(unit)
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
                scored_tasks = []
                for p, t_type, prio in tasks:
                    dist = _distance(unit.position, p)
                    
                    # Score components
                    score = prio
                    score -= dist * 5  # travel cost
                    if dist <= 3:
                        score += 30  # locality benefit
                        
                    # Interference risk
                    interference = sum(1 for t in targeted_tiles if _distance(p, t) <= 1)
                    score -= interference * 20
                    
                    scored_tasks.append((score, p, t_type))
                    
                best = max(scored_tasks, key=lambda x: x[0])
                target = best[1]
                t_type = best[2]
                
                if t_type != "DROP":
                    targeted_tiles.add(target)
                if t_type == "PLANT":
                    seed_reserves += 1
                    
                if unit.position == target:
                    action = [t_type] if t_type != "PLANT" else ["PLANT", "MELON"]
                else:
                    action = [_choose_movement(unit.position, target)]
                    
            self.record_action(uid, target, action[0])
            unit_actions.append(action)

        all_targets = [self.last_targets.get(id(u)) for u in all_units if self.last_targets.get(id(u))]
        conflicts = len(all_targets) - len(set(all_targets))
        if conflicts > 0:
            self.j4_metrics["target_conflicts"] += conflicts

        return {"farmer": unit_actions[0], "hands": unit_actions[1:]}


def run_episode(scheduler_cls, fixed_workers: int, seed: int):
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    trainer = env.train([None, "random"])
    
    agent = ScalabilityCoordinator(scheduler_cls, fixed_workers)
    
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
    
    # Retrieve metrics from the manager instance
    manager = agent.scheduler
    return {
        "final_cash": final_cash,
        "metrics": manager.j4_metrics
    }

def evaluate(scheduler_cls, scheduler_name: str, workers: int):
    results = [run_episode(scheduler_cls, workers, s) for s in SEEDS]
    
    rewards = [r["final_cash"] for r in results]
    mean_r = statistics.mean(rewards)
    
    # Average metrics
    mean_prod = statistics.mean(r["metrics"]["productive"] for r in results)
    mean_move = statistics.mean(r["metrics"]["movement"] for r in results)
    mean_pass = statistics.mean(r["metrics"]["passes"] for r in results)
    mean_conflicts = statistics.mean(r["metrics"]["target_conflicts"] for r in results)
    mean_switches = statistics.mean(r["metrics"]["task_switches"] for r in results)
    
    total_actions = mean_prod + mean_move + mean_pass
    utilization = (mean_prod + mean_move) / total_actions if total_actions > 0 else 0
    move_ratio = mean_move / mean_prod if mean_prod > 0 else 0
    
    return {
        "policy": scheduler_name,
        "workers": workers,
        "mean_reward": mean_r,
        "productive": mean_prod,
        "movement": mean_move,
        "passes": mean_pass,
        "utilization": utilization,
        "move_ratio": move_ratio,
        "conflicts": mean_conflicts,
        "switches": mean_switches
    }

def main():
    worker_counts = [1, 2, 3, 4]
    policies = [
        (PolicyA_GlobalV1, "A_Global"),
        (PolicyB_LocalFirst, "B_LocalFirst"),
        (PolicyC_Adaptive, "C_Adaptive")
    ]
    
    all_results = []
    
    for cls, name in policies:
        print(f"\nEvaluating {name}...")
        for w in worker_counts:
            print(f"  {w} workers...", end=" ", flush=True)
            res = evaluate(cls, name, w)
            all_results.append(res)
            print(f"${res['mean_reward']:.0f} (Conflicts: {res['conflicts']:.1f})")
            
    # Build report
    report = "# Experiment J4 — Worker Locality Report\n\n"
    report += "| Policy | Workers | Reward | Prod | Move | Util% | Move/Prod | Conflicts | Switches |\n"
    report += "|--------|---------|--------|------|------|-------|-----------|-----------|----------|\n"
    
    for r in all_results:
        report += f"| {r['policy']} | {r['workers']} | ${r['mean_reward']:.0f} | {r['productive']:.1f} | {r['movement']:.1f} | {r['utilization']*100:.1f}% | {r['move_ratio']:.2f} | {r['conflicts']:.1f} | {r['switches']:.1f} |\n"
        
    with open("j4_report.md", "w") as f:
        f.write(report)
        
    print("\nResults saved to j4_report.md")
    
if __name__ == "__main__":
    main()
