import sys
import os
import multiprocessing
import statistics
import collections

sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser, Position
from fieldops.constants import CROP_DATA, SHED_ADJACENT_TILES

def _distance(p1, p2):
    return abs(p1.x - p2.x) + abs(p1.y - p2.y)

def _choose_movement(current, target):
    dx = target.x - current.x
    dy = target.y - current.y
    if abs(dx) > abs(dy): return "EAST" if dx > 0 else "WEST"
    elif dy != 0: return "SOUTH" if dy > 0 else "NORTH"
    elif dx != 0: return "EAST" if dx > 0 else "WEST"
    return "PASS"

def get_quad(p):
    if p.x < 5 and p.y < 5: return "NW"
    if p.x >= 5 and p.y < 5: return "NE"
    if p.x < 5 and p.y >= 5: return "SW"
    return "SE"

SHED_POS = [Position(x=x, y=y) for x, y in SHED_ADJACENT_TILES]

# ---------------------------------------------------------
# Agent Factory
# ---------------------------------------------------------
def create_agent(is_fix):
    def agent_logic(obs, cfg=None):
        state = ObservationParser.parse(obs)
        if state.step >= 719: return {"farmer": ["PASS"], "hands": [], "market": []}
        
        my_farm = state.my_farm
        actions = {"farmer": ["PASS"], "hands": [], "market": []}
        
        # 1. Market
        if my_farm.shed is not None:
            for item, count in my_farm.shed.items.items():
                if count > 0 and item != "FERTILIZER":
                    actions["market"].append(["SELL", item, count])
                    
        quads_unlocked = len(my_farm.unlocked_quadrants)
        if quads_unlocked < 4:
            land_cost = 1000 if quads_unlocked == 1 else (2000 if quads_unlocked == 2 else 4000)
            seed_buffer = 2000
            if my_farm.money >= (land_cost + seed_buffer + 100) and state.day <= 18:
                actions["market"].append(["BUY_LAND"])
                
        target_hands = min(5, quads_unlocked + 1)
        if my_farm.hires_today < target_hands and my_farm.money >= 50:
            actions["market"].append(["HIRE"])
            
        empty_tiles = []
        unwatered = []
        harvestable = []
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                pos = Position(x=x, y=y)
                if tile.is_empty(): empty_tiles.append(pos)
                elif tile.kind == "PLANT":
                    md = CROP_DATA[tile.crop]["max_yield_day"]
                    if tile.planted_day is not None and (state.day - tile.planted_day) >= md:
                        harvestable.append(pos)
                    elif not tile.watered_today:
                        unwatered.append(pos)

        target_crop = "MELON" if state.step <= 408 else ("CARROT" if state.step <= 600 else None)
        if target_crop and empty_tiles:
            cs = my_farm.seeds.get(target_crop, 0) if my_farm.seeds else 0
            needed = len(empty_tiles) - cs
            if needed > 0:
                sc = CROP_DATA[target_crop]["seed_cost"]
                b = min(needed, int(my_farm.money // sc))
                if b > 0: actions["market"].append(["BUY_SEED", target_crop, b])
                
        # 2. Scheduler
        all_units = [my_farm.farmer] + list(my_farm.hands)
        u_acts = [None] * len(all_units)
        targeted = set()
        
        m_avail = my_farm.seeds.get("MELON", 0) if my_farm.seeds else 0
        c_avail = my_farm.seeds.get("CARROT", 0) if my_farm.seeds else 0
        m_res = 0
        c_res = 0

        if not is_fix:
            # BASELINE (Greedy Seq)
            for i, unit in enumerate(all_units):
                valid_w = [p for p in unwatered if p not in targeted]
                if valid_w:
                    t = min(valid_w, key=lambda p: _distance(unit.position, p))
                    targeted.add(t)
                    u_acts[i] = ["WATER"] if unit.position == t else [_choose_movement(unit.position, t)]
                    continue
                valid_h = [p for p in harvestable if p not in targeted]
                if valid_h:
                    t = min(valid_h, key=lambda p: _distance(unit.position, p))
                    targeted.add(t)
                    u_acts[i] = ["HARVEST"] if unit.position == t else [_choose_movement(unit.position, t)]
                    continue
                has_produce = any(v > 0 for k, v in unit.inventory.items.items() if k != "FERTILIZER")
                if has_produce:
                    t = min(SHED_POS, key=lambda p: _distance(unit.position, p))
                    u_acts[i] = ["DROP"] if unit.position in SHED_POS else [_choose_movement(unit.position, t)]
                    continue
                valid_e = [p for p in empty_tiles if p not in targeted]
                if valid_e:
                    if (m_avail - m_res) > 0:
                        t = min(valid_e, key=lambda p: _distance(unit.position, p))
                        targeted.add(t)
                        m_res += 1
                        u_acts[i] = ["PLANT", "MELON"] if unit.position == t else [_choose_movement(unit.position, t)]
                        continue
                    elif (c_avail - c_res) > 0:
                        t = min(valid_e, key=lambda p: _distance(unit.position, p))
                        targeted.add(t)
                        c_res += 1
                        u_acts[i] = ["PLANT", "CARROT"] if unit.position == t else [_choose_movement(unit.position, t)]
                        continue
                u_acts[i] = ["PASS"]
        else:
            # FIX (Global Distance Sort)
            for qs, act_str, chk_shed, chk_seed in [
                (unwatered, "WATER", False, None),
                (harvestable, "HARVEST", False, None),
                (SHED_POS, "DROP", True, None),
                (empty_tiles, "PLANT", False, True)
            ]:
                pairs = []
                for i, unit in enumerate(all_units):
                    if u_acts[i] is not None: continue
                    if chk_shed:
                        if not any(v > 0 for k, v in unit.inventory.items.items() if k != "FERTILIZER"): continue
                    for t in qs:
                        if not chk_shed and t in targeted: continue
                        pairs.append((_distance(unit.position, t), i, t))
                pairs.sort(key=lambda x: x[0])
                for dist, i, t in pairs:
                    if u_acts[i] is None:
                        if chk_shed:
                            u_acts[i] = ["DROP"] if all_units[i].position in SHED_POS else [_choose_movement(all_units[i].position, t)]
                        else:
                            if t not in targeted:
                                if chk_seed:
                                    if (m_avail - m_res) > 0:
                                        targeted.add(t)
                                        m_res += 1
                                        u_acts[i] = ["PLANT", "MELON"] if all_units[i].position == t else [_choose_movement(all_units[i].position, t)]
                                    elif (c_avail - c_res) > 0:
                                        targeted.add(t)
                                        c_res += 1
                                        u_acts[i] = ["PLANT", "CARROT"] if all_units[i].position == t else [_choose_movement(all_units[i].position, t)]
                                else:
                                    targeted.add(t)
                                    u_acts[i] = [act_str] if all_units[i].position == t else [_choose_movement(all_units[i].position, t)]
            for i in range(len(all_units)):
                if u_acts[i] is None: u_acts[i] = ["PASS"]
                
        actions["farmer"] = u_acts[0]
        actions["hands"] = u_acts[1:]
        return actions
    return agent_logic

# ---------------------------------------------------------
# Simulation Runner
# ---------------------------------------------------------
def run_sim(args):
    seed, is_fix = args
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    
    metrics = {
        "active_plants": [],
        "watered_today": [],
        "harvested": 0,
        "planted": 0,
        "melon_revenue": 0,
        "melon_sold_qty": 0,
        "seed_expense": 0,
        "stalled_crop_days": 0,
    }
    
    planting_records = {} # pos -> (planted_day, crop)
    doomed_late = 0
    doomed_stalled = 0
    
    agent = create_agent(is_fix)
    
    def wrapper(obs, cfg=None):
        if not isinstance(obs, dict): return agent(obs, cfg)
        s = obs.get("step", 0)
        state = ObservationParser.parse(obs)
        my_farm = state.my_farm
        
        # Track Active Plants & Stalls
        act = 0
        wtd = 0
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                if tile.kind == "PLANT":
                    act += 1
                    if tile.watered_today: wtd += 1
                    # Record stalls at end of day
                    if s > 0 and s % 24 == 23:
                        if not tile.watered_today:
                            metrics["stalled_crop_days"] += 1
        metrics["active_plants"].append(act)
        metrics["watered_today"].append(wtd)
        
        # Track Sales (before agent executes)
        if my_farm.shed:
            for k, v in my_farm.shed.items.items():
                if k == "MELON" and v > 0:
                    # we will sell v. How much revenue?
                    pass # We track revenue by monitoring money delta if possible, but market price fluctuates.
                    # Kaggriculture computes market price.
        prev_money = my_farm.money
        
        actions = agent(obs)
        
        # Track plantings and harvests
        for unit_act in [actions.get("farmer", ["PASS"])] + actions.get("hands", []):
            if not unit_act: continue
            a = unit_act[0]
            if a == "PLANT": 
                metrics["planted"] += 1
            elif a == "HARVEST":
                metrics["harvested"] += 1
        
        # Track Seed Expense
        for ma in actions.get("market", []):
            if ma[0] == "BUY_SEED":
                metrics["seed_expense"] += CROP_DATA[ma[1]]["seed_cost"] * ma[2]
                
        if s == 718:
            unsold = 0
            for u in [my_farm.farmer] + list(my_farm.hands):
                unsold += u.inventory.items.get("MELON", 0)
            if my_farm.shed:
                unsold += my_farm.shed.items.get("MELON", 0)
            metrics["unsold_melons_end"] = unsold
            
            last_tiles = []
            for y, row in enumerate(my_farm.tiles):
                for x, tile in enumerate(row):
                    if tile.kind == "PLANT":
                        last_tiles.append((tile.planted_day, tile.crop))
            metrics["last_tiles"] = last_tiles
            
        return actions

    steps = env.run([wrapper, "pass"])
    
    # Accurate revenue tracking by looking at step rewards
    final_reward = steps[-1][0].reward
    
    # Calculate unsold inventory
    unsold_melons = metrics.get("unsold_melons_end", 0)
        
    # How many crops unharvested?
    unharvested = 0
    if "last_tiles" in metrics:
        for tile in metrics["last_tiles"]:
            unharvested += 1
            md = CROP_DATA[tile[1]]["max_yield_day"]
            if tile[0] is not None:
                if tile[0] + md > 30:
                    doomed_late += 1
                else:
                    doomed_stalled += 1
                        
    # Estimate average sell price (Total Revenue - initial 10k + expenses = Sales)
    # This is rough because of land and hiring, but we can assume land = 7000 (3 quads), hires = 5 * (fib... approx 1000).
    total_spent_land = 1000 + 2000 + 4000
    total_spent_hire = sum(1 * min(5, q+1) for q in range(1, 4)) * 50 # Approx 1500
    # Actually, Kaggle state has exact spent? No. 
    # But total reward = 10000 + Sales - Seeds - Land - Hires.
    # We can just return the raw metrics and average them.
    
    return {
        "reward": final_reward,
        "active_plants": statistics.mean(metrics["active_plants"]),
        "watered_plants_day": sum(metrics["watered_today"]) / 30.0,
        "stalled_crop_days": metrics["stalled_crop_days"],
        "harvests": metrics["harvested"],
        "planted": metrics["planted"],
        "seed_expense": metrics["seed_expense"],
        "unsold_melons": unsold_melons,
        "unharvested": unharvested,
        "doomed_late": doomed_late,
        "doomed_stalled": doomed_stalled
    }

def main():
    num_sims = 10
    print("="*80)
    print("REWARD COLLAPSE PROFILING (10 seeds: 42-51)")
    print("="*80)
    
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        args_base = [(42+i, False) for i in range(num_sims)]
        args_fix = [(42+i, True) for i in range(num_sims)]
        
        res_base = pool.map(run_sim, args_base)
        res_fix = pool.map(run_sim, args_fix)
        
    def avg(res, key):
        return sum(r[key] for r in res) / len(res)

    print(f"\n{'Metric':<25} | {'Baseline':<12} | {'Assign Fix':<12} | {'Delta'}")
    print("-" * 65)
    for k in res_base[0].keys():
        b = avg(res_base, k)
        f = avg(res_fix, k)
        d = f - b
        fmt = "12.1f" if "active" in k or "watered" in k else "12.0f"
        print(f"{k:<25} | {b:{fmt}} | {f:{fmt}} | {d:{fmt}}")
        
    # Financial Analysis (Approximate Attribution)
    # The reward gap = Reward_fix - Reward_base
    delta_reward = avg(res_fix, "reward") - avg(res_base, "reward")
    
    # 1. Seed Capital Loss = Delta Seed Expense (money spent on seeds that failed or succeeded)
    delta_seeds = avg(res_fix, "seed_expense") - avg(res_base, "seed_expense")
    
    # 2. Lost potential revenue from Unharvested crops
    # A harvested melon crop yields 6 melons. 
    # Melons sell for ~$200 on average (market drops from 250).
    avg_price = 200
    
    # Water Starvation loss = (Delta Doomed Stalled) * 6 melons * avg_price
    delta_stalled_crops = avg(res_fix, "doomed_stalled") - avg(res_base, "doomed_stalled")
    loss_water_starvation = delta_stalled_crops * 6 * avg_price
    
    # Wasted Late Planting = (Delta Doomed Late) * 6 melons * avg_price
    delta_late_crops = avg(res_fix, "doomed_late") - avg(res_base, "doomed_late")
    loss_late_planting = delta_late_crops * 6 * avg_price
    
    # Unsold Inventory = Delta Unsold Melons * avg_price
    delta_unsold = avg(res_fix, "unsold_melons") - avg(res_base, "unsold_melons")
    loss_unsold = delta_unsold * avg_price
    
    # Market Price Collapse
    # We know Fix harvested more, so Revenue should have spiked by Delta Harvests * 6 * avg_price.
    # If it didn't, the price collapsed.
    delta_harvests = avg(res_fix, "harvests") - avg(res_base, "harvests")
    expected_extra_revenue = delta_harvests * 6 * 250 # Using max price to see gap
    
    # Actual delta revenue = Delta Reward + Delta Seed + Delta Hire + Delta Land
    # Assuming Hire/Land are similar.
    actual_delta_revenue = delta_reward + delta_seeds
    
    price_collapse_gap = expected_extra_revenue - actual_delta_revenue
    
    print("\n" + "="*80)
    print(f"REWARD DELTA CONTRIBUTION ANALYSIS (Approximate)")
    print(f"Total Reward Delta: ${delta_reward:,.0f}")
    print("="*80)
    print(f"1. Water Starvation (Stalled):      -${loss_water_starvation:,.0f} (Expected revenue lost to unwatered crops)")
    print(f"2. Wasted Late Planting (Time):     -${loss_late_planting:,.0f} (Expected revenue lost to day>30 end)")
    print(f"3. Market Price Collapse / Unsold:  -${price_collapse_gap:,.0f} (Revenue lost to tanked market price & unsold inventory)")
    print(f"4. Direct Seed Capital Loss:        -${delta_seeds:,.0f} (Cash spent on seeds over baseline)")

if __name__ == "__main__":
    main()
