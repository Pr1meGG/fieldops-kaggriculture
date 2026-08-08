import sys, os, random, math, statistics
from multiprocessing import Pool
sys.path.insert(0, os.path.abspath("src"))

from kaggle_environments import make
from fieldops.state import ObservationParser, Position
SEEDS = [42, 123, 999, 1024, 777, 888, 555, 333, 111, 222, 
         1234, 5678, 91011, 131415, 161718, 192021, 222324, 252627, 282930, 313233]

class SchedulerBase:
    def __init__(self, target_cows: int, target_sheep: int, layout: str):
        self.target_cows = target_cows
        self.target_sheep = target_sheep
        self.layout = layout
        self.metrics = {
            "productive": 0, "movement": 0, "passes": 0, "feed_cost": 0, "act_counts": {
                "NORTH": 0, "SOUTH": 0, "EAST": 0, "WEST": 0, "PASS": 0,
                "PLANT": 0, "WATER": 0, "HARVEST": 0, "FERTILIZE": 0,
                "BUILD_PASTURE": 0, "PICKUP": 0, "PLACE": 0, "FEED": 0,
                "COLLECT_FERTILIZER": 0, "CARE": 0, "DROP": 0, "SELL": 0
            }
        }
    def record_action(self, op: str):
        self.metrics["act_counts"][op] = self.metrics["act_counts"].get(op, 0) + 1
        if op in ("NORTH", "SOUTH", "EAST", "WEST"): self.metrics["movement"] += 1
        elif op == "PASS": self.metrics["passes"] += 1
        else: self.metrics["productive"] += 1

def _choose_movement(pos: Position, target: Position) -> str:
    if pos.x < target.x: return "EAST"
    if pos.x > target.x: return "WEST"
    if pos.y < target.y: return "SOUTH"
    if pos.y > target.y: return "NORTH"
    return "PASS"

class Policy_K3(SchedulerBase):
    def _get_pastures_to_build(self, state, num_target=2):
        built = sum(1 for row in state.my_farm.tiles for t in row if t.kind == "PASTURE")
        needed = num_target - built
        if needed <= 0: return []
        
        empty_tiles = [Position(x=x, y=y) for y, row in enumerate(state.my_farm.tiles) for x, t in enumerate(row) if t.is_empty()]
        
        if self.layout in ("CONTROL", "A"):
            return [p for p in empty_tiles if p.x <= 1 and p.y <= 1][:needed]
        else: # B and C
            empty_tiles.sort(key=lambda p: abs(p.x - 4) + abs(p.y - 4))
            return empty_tiles[:needed]

    def execute(self, state, all_units):
        my_farm = state.my_farm
        unit_actions = []
        targeted_tiles = set()
        
        seed_reserves = my_farm.seeds.get("MELON", 0) if my_farm.seeds else 0
        wheat_reserves = my_farm.shed.items.get("WHEAT", 0)
        
        pastures_to_build = self._get_pastures_to_build(state, self.target_cows + self.target_sheep)

        for unit in all_units:
            action = ["PASS"]
            tasks = []
            
            # High Priority: WHEAT DELIVERY
            if unit.inventory.items.get("WHEAT", 0) > 0:
                hungry = [Position(x=x, y=y) for y, row in enumerate(my_farm.tiles) for x, t in enumerate(row)
                          if t.has_animal() and not t.fed_today]
                for p in hungry:
                    if p not in targeted_tiles: tasks.append((p, "FEED", 1000))

            # Medium-High: WHEAT PICKUP (if hungry animals exist and no wheat in inventory)
            hungry_all = sum(1 for row in my_farm.tiles for t in row if t.has_animal() and not t.fed_today)
            if hungry_all > 0 and unit.inventory.items.get("WHEAT", 0) == 0 and wheat_reserves > 0:
                tasks.append((Position(x=4, y=4), "PICKUP_WHEAT", 900))
                
            # Animal placement
            for a_type in ["COW", "SHEEP"]:
                if unit.inventory.items.get(a_type, 0) > 0:
                    empty_pastures = [Position(x=x, y=y) for y, row in enumerate(my_farm.tiles) for x, t in enumerate(row)
                                      if t.kind == "PASTURE" and not getattr(t, 'animal', None)]
                    for p in empty_pastures:
                        if p not in targeted_tiles: tasks.append((p, f"PLACE_{a_type}", 950))
                
            if unit.inventory.items.get("COW", 0) == 0 and unit.inventory.items.get("SHEEP", 0) == 0:
                empty_pastures = sum(1 for row in my_farm.tiles for t in row if t.kind == "PASTURE" and not getattr(t, 'animal', None))
                cows_in_shed = my_farm.shed.items.get("COW", 0)
                sheep_in_shed = my_farm.shed.items.get("SHEEP", 0)
                
                if empty_pastures > 0:
                    if cows_in_shed > 0:
                        tasks.append((Position(x=4, y=4), "PICKUP_COW", 850))
                    elif sheep_in_shed > 0:
                        tasks.append((Position(x=4, y=4), "PICKUP_SHEEP", 850))
            
            if sum(unit.inventory.items.values()) > 0 and not any("WHEAT" in k or "COW" in k or "SHEEP" in k for k in unit.inventory.items.keys()):
                tasks.append((Position(x=4, y=4), "DROP", 80))
            
            needs_water = [Position(x=x, y=y) for y, row in enumerate(my_farm.tiles) for x, t in enumerate(row)
                           if t.is_plant() and not getattr(t, 'watered_today', False)]
            harvestable = [Position(x=x, y=y) for y, row in enumerate(my_farm.tiles) for x, t in enumerate(row)
                           if t.is_plant() and (state.day - getattr(t, 'planted_day', 0)) >= 10]
            
            has_animal_harvest = [Position(x=x, y=y) for y, row in enumerate(my_farm.tiles) for x, t in enumerate(row)
                                  if t.has_animal() and getattr(t, 'yield_units', 0) > 0]
            has_fertilizer = [Position(x=x, y=y) for y, row in enumerate(my_farm.tiles) for x, t in enumerate(row)
                              if t.has_animal() and getattr(t, 'fertilizer_available', False)]

            for p in needs_water:
                if p not in targeted_tiles: tasks.append((p, "WATER", 60))
            for p in harvestable:
                if p not in targeted_tiles: tasks.append((p, "HARVEST", 90))
            for p in has_animal_harvest:
                if p not in targeted_tiles: tasks.append((p, "HARVEST", 90))
            for p in has_fertilizer:
                if p not in targeted_tiles: tasks.append((p, "COLLECT_FERTILIZER", 85))
            for p in pastures_to_build:
                if p not in targeted_tiles: tasks.append((p, "BUILD_PASTURE", 85))

            active_melons = sum(1 for row in my_farm.tiles for t in row if t.is_plant() and t.crop == "MELON")
            target_melons_left = 12 - active_melons
            if target_melons_left > 0 and seed_reserves > 0:
                empty_tiles = [Position(x=x, y=y) for y, row in enumerate(my_farm.tiles) for x, t in enumerate(row) if t.is_empty()]
                
                if self.layout in ("CONTROL", "A"):
                    plantable = [p for p in empty_tiles if not (p.x <= 1 and p.y <= 1)]
                elif self.layout == "B":
                    plantable = empty_tiles
                elif self.layout == "C":
                    plantable = sorted(empty_tiles, key=lambda p: abs(p.x - 4) + abs(p.y - 4))
                
                for p in plantable[:target_melons_left]:
                    if p not in targeted_tiles: tasks.append((p, "PLANT", 50))
            
            needs_care = [Position(x=x, y=y) for y, row in enumerate(my_farm.tiles) for x, t in enumerate(row)
                          if t.has_animal() and not getattr(t, 'cared_today', False)]
            for p in needs_care:
                if p not in targeted_tiles: tasks.append((p, "CARE", 40))
                
            tasks_with_dist = []
            for t in tasks:
                pos, t_type, prio = t
                dist = abs(unit.position.x - pos.x) + abs(unit.position.y - pos.y)
                tasks_with_dist.append((pos, t_type, prio, dist))
                
            if tasks_with_dist:
                local_tasks = [t for t in tasks_with_dist if t[3] <= 2]
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
                    seed_reserves -= 1
                if t_type == "FEED":
                    wheat_reserves -= 1
                    
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

class K3Coordinator:
    def __init__(self, fixed_workers: int, target_cows: int, target_sheep: int, layout: str):
        self.scheduler = Policy_K3(target_cows, target_sheep, layout)
        self.target_cows = target_cows
        self.target_sheep = target_sheep
        self.fixed_workers = fixed_workers

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

        # Hire fixed_workers
        actions = {"farmer": ["PASS"], "hands": [], "market": []}
        active_hands = len(my_farm.hands)
        hires_today = getattr(my_farm, 'hires_today', 0)
        target_hands = self.fixed_workers - 1
        
        if active_hands < target_hands and my_farm.money > 0:
            actions["market"].append(["HIRE"])

        units = [my_farm.farmer] + list(my_farm.hands)
        sched_actions = self.scheduler.execute(state, units)
        actions["farmer"] = sched_actions["farmer"]
        actions["hands"] = sched_actions["hands"]

        owned_cows = my_farm.shed.items.get("COW", 0) + sum(1 for row in my_farm.tiles for t in row if t.has_animal() and t.animal == "COW")
        owned_sheep = my_farm.shed.items.get("SHEEP", 0) + sum(1 for row in my_farm.tiles for t in row if t.has_animal() and t.animal == "SHEEP")

        pastures = sum(1 for row in my_farm.tiles for t in row if t.kind == "PASTURE")
        animals_to_buy = []
        if owned_cows < self.target_cows and pastures > (owned_cows + owned_sheep):
            animals_to_buy.append(("COW", self.target_cows - owned_cows, 400))
        elif owned_sheep < self.target_sheep and pastures > (owned_cows + owned_sheep):
            animals_to_buy.append(("SHEEP", self.target_sheep - owned_sheep, 500))

        money = my_farm.money

        for anim, count, cost in animals_to_buy:
            if money >= count * cost:
                actions["market"].append(["BUY_ANIMAL", anim, count])
                money -= count * cost
                if anim == "COW": self.cows_bought += count
                else: self.sheep_bought += count

        current_plants = sum(1 for row in my_farm.tiles for t in row if t.is_plant())
        seeds_held = my_farm.seeds.get("MELON", 0) if my_farm.seeds else 0
        need_seeds = 12 - seeds_held - current_plants
        if need_seeds > 0 and money >= need_seeds * 10:
            actions["market"].append(["BUY_SEED", "MELON", need_seeds])
            money -= need_seeds * 10

        total_animals = owned_cows + owned_sheep
        wheat_held = my_farm.shed.items.get("WHEAT", 0)
        for u in units:
            wheat_held += u.inventory.items.get("WHEAT", 0)

        if total_animals > 0 and wheat_held < total_animals * 10:
            need_wheat = (total_animals * 10) - wheat_held
            if money >= need_wheat * 25:
                actions["market"].append(["BUY_PRODUCT", "WHEAT", need_wheat])
                money -= need_wheat * 25
                self.wheat_bought += need_wheat
                self.scheduler.metrics["feed_cost"] += need_wheat * 25

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

def run_episode(config_name: str, layout: str, workers: int, cows: int, sheep: int, seed: int):
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    trainer = env.train([None, "scratch/agent_pass.py"])

    agent = K3Coordinator(workers, cows, sheep, layout)
    obs = trainer.reset()

    while not env.done:
        step = obs.get("step", 0) if isinstance(obs, dict) else obs.step
        if step >= 500:
            print(f"      Step {step}")
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
        "cows_bought": agent.cows_bought,
        "sheep_bought": agent.sheep_bought,
        "feed_bought": agent.wheat_bought,
        "metrics": agent.scheduler.metrics
    }

def run_episode_wrapper(args):
    return run_episode(*args)

def evaluate(config_name: str, layout: str, workers: int, cows: int, sheep: int):
    args_list = [(config_name, layout, workers, cows, sheep, s) for s in SEEDS]
    with Pool(processes=20) as pool:
        results = pool.map(run_episode_wrapper, args_list)
    mean_r = statistics.mean(r["final_cash"] for r in results)

    mean_prod = statistics.mean(r["metrics"]["productive"] for r in results)
    mean_move = statistics.mean(r["metrics"]["movement"] for r in results)
    mean_pass = statistics.mean(r["metrics"]["passes"] for r in results)

    for r in results:
        prod = r["metrics"]["productive"]
        move = r["metrics"]["movement"]
        pas = r["metrics"]["passes"]
        tot = prod + move + pas
        r["productive"] = prod
        r["movement"] = move
        r["utilization"] = (prod + move) / tot if tot > 0 else 0

    avg_acts = {
        k: sum(r["metrics"]["act_counts"].get(k, 0) for r in results) / len(results)
        for k in results[0]["metrics"]["act_counts"]
    }

    return {
        "config": config_name,
        "mean_reward": sum(r["final_cash"] for r in results) / len(results),
        "min_reward": min(r["final_cash"] for r in results),
        "max_reward": max(r["final_cash"] for r in results),
        "utilization": sum(r["utilization"] for r in results) / len(results),
        "productive": sum(r["productive"] for r in results) / len(results),
        "movement": sum(r["movement"] for r in results) / len(results),
        "sold_melons": sum(r["sold_melons"] for r in results) / len(results),
        "sold_milk": sum(r["sold_milk"] for r in results) / len(results),
        "sold_wool": sum(r["sold_wool"] for r in results) / len(results),
        "sold_fert": sum(r["sold_fert"] for r in results) / len(results),
        "feed_bought": sum(r["feed_bought"] for r in results) / len(results),
        "cows_bought": sum(r["cows_bought"] for r in results) / len(results),
        "sheep_bought": sum(r["sheep_bought"] for r in results) / len(results),
        "acts": avg_acts
    }

def main():
    configs = [
        ("CONFIG 0 (1W, 0L)", "CONTROL", 1, 0, 0),
        ("CONFIG 1 (1W, 1C+1S)", "C", 1, 1, 1),
        ("CONFIG 2 (2W, 1C+1S)", "C", 2, 1, 1),
        ("CONFIG 3 (2W, 2C+2S)", "C", 2, 2, 2),
    ]

    all_results = []
    print("Running K4 Experiment...")
    for name, lay, w, c, s in configs:
        print(f"Evaluating {name}...")
        res = evaluate(name, lay, w, c, s)
        print(f"  Mean: ${res['mean_reward']:.0f}, Min: ${res['min_reward']:.0f}, Max: ${res['max_reward']:.0f}")
        all_results.append(res)
        
    report = "# Experiment K4 — 2-Worker Livestock Expansion Report\n\n"
    
    report += "| Config | Mean | Min | Max | Util% | Prod | Move | M/P Ratio | Melons | Milk | Wool | Fert | Feed Buy | Animal Buy |\n"
    report += "|--------|------|-----|-----|-------|------|------|-----------|--------|------|------|------|----------|------------|\n"
    for r in all_results:
        mp = r['movement'] / r['productive'] if r['productive'] > 0 else 0
        report += f"| {r['config']} | ${r['mean_reward']:.0f} | ${r['min_reward']:.0f} | ${r['max_reward']:.0f} | {r['utilization']*100:.1f}% | {r['productive']:.1f} | {r['movement']:.1f} | {mp:.2f} | {r['sold_melons']:.1f} | {r['sold_milk']:.1f} | {r['sold_wool']:.1f} | {r['sold_fert']:.1f} | {r['feed_bought']:.1f} | {r['cows_bought']+r['sheep_bought']:.1f} |\n"

    report += "\n## Action Breakdown\n"
    report += "| Config | PLANT | WATER | HARVEST | FEED | CARE | COL_FERT | DROP | PICKUP | PLACE | PASS |\n"
    report += "|--------|-------|-------|---------|------|------|----------|------|--------|-------|------|\n"
    for r in all_results:
        a = r["acts"]
        report += f"| {r['config']} | {a['PLANT']:.1f} | {a['WATER']:.1f} | {a['HARVEST']:.1f} | {a['FEED']:.1f} | {a['CARE']:.1f} | {a['COLLECT_FERTILIZER']:.1f} | {a['DROP']:.1f} | {a['PICKUP']:.1f} | {a['PLACE']:.1f} | {a['PASS']:.1f} |\n"

    with open("k4_report.md", "w") as f:
        f.write(report)

    print("\nResults saved to k4_report.md")

if __name__ == "__main__":
    main()
