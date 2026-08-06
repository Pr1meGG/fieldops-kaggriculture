"""
Deep profit loss analysis.
Tracks every melon sold, price decay, wasted planting, worker overspend,
and idle tile-turns to quantify the five largest sources of lost money.
"""
import sys, os
sys.path.insert(0, os.path.abspath("src"))

from kaggle_environments import make
from fieldops.state import ObservationParser
from fieldops.constants import CROP_DATA

def run():
    env = make("kaggriculture", debug=True)
    steps = env.run(["src/fieldops/agent.py", "pass"])

    # --- Track sell prices over time ---
    sell_events = []  # (step, day, crop, qty, unit_price, total)
    
    # --- Track hire costs (Fibonacci per day) ---
    hire_events = []  # (step, day, fib_cost)
    hires_per_day = {}
    
    # --- Track seed purchases ---
    seed_events = []  # (step, day, crop, qty, unit_cost, total)
    
    # --- Track land purchases ---
    land_events = []
    
    # --- Track planting events ---
    plant_events = []  # (step, day, crop)
    
    # --- Track harvest events ---
    harvest_events = []  # (step, day)
    
    # --- Tile utilization per step ---
    total_unlocked_tile_turns = 0
    total_occupied_tile_turns = 0
    total_empty_tile_turns = 0
    
    # --- Plants that were planted but never harvested ---
    # Track planted_day per tile
    active_plants = {}  # (x,y) -> (crop, planted_day, step_planted)
    harvested_plants = set()
    
    # --- Worker PASS tracking ---
    total_unit_actions = 0
    total_pass_actions = 0
    total_move_actions = 0
    total_work_actions = 0  # WATER, HARVEST, PLANT, DROP
    
    # --- Late planting (melons planted after day 17 that can't mature) ---
    late_melon_plants = []
    
    # Fibonacci helper
    def fib(n):
        a, b = 1, 1
        for _ in range(n):
            a, b = b, a + b
        return a

    prev_money = 3000
    
    for i, step in enumerate(steps):
        obs_dict = step[0].observation
        if obs_dict.get('step') is None:
            continue
        step_num = obs_dict['step']
        if step_num >= 719:
            continue

        state = ObservationParser.parse(obs_dict)
        day = state.day
        my_farm = state.my_farm
        
        # Tile utilization
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                if tile.kind == "LOCKED":
                    continue
                total_unlocked_tile_turns += 1
                if tile.kind == "PLANT":
                    total_occupied_tile_turns += 1
                else:
                    total_empty_tile_turns += 1

        action = step[0].action
        if not action:
            continue
            
        market_acts = action.get("market", [])
        for m in market_acts:
            if not m:
                continue
            op = m[0]
            if op == "SELL":
                crop, qty = m[1], m[2]
                price = state.market.prices.get(crop, 0)
                total = qty * price
                sell_events.append((step_num, day, crop, qty, price, total))
            elif op == "BUY_SEED":
                crop, qty = m[1], m[2]
                cost = CROP_DATA[crop]["seed_cost"]
                seed_events.append((step_num, day, crop, qty, cost, qty * cost))
            elif op == "HIRE":
                day_hires = hires_per_day.get(day, 0)
                cost = fib(day_hires)
                hire_events.append((step_num, day, cost))
                hires_per_day[day] = day_hires + 1
            elif op == "BUY_LAND":
                quads = len(my_farm.unlocked_quadrants)
                cost = 1000 if quads == 1 else (2000 if quads == 2 else 4000)
                land_events.append((step_num, day, cost, my_farm.money))

        unit_acts = [action.get("farmer", ["PASS"])] + action.get("hands", [])
        for act in unit_acts:
            total_unit_actions += 1
            if not act or act == ["PASS"]:
                total_pass_actions += 1
            elif act[0] in ("NORTH", "SOUTH", "EAST", "WEST"):
                total_move_actions += 1
            else:
                total_work_actions += 1
                if act[0] == "PLANT":
                    crop = act[1] if len(act) > 1 else "MELON"
                    plant_events.append((step_num, day, crop))
                    if crop == "MELON" and day > 17:
                        late_melon_plants.append((step_num, day))
                elif act[0] == "HARVEST":
                    harvest_events.append((step_num, day))

    final_reward = steps[-1][0].reward
    
    # === ANALYSIS ===
    print("=" * 70)
    print("PROFIT LOSS ANALYSIS")
    print("=" * 70)
    
    # 1. PRICE DECAY LOSS
    print("\n--- 1. MELON PRICE DECAY LOSS ---")
    base_price = 250
    total_revenue = sum(e[5] for e in sell_events)
    total_melons_sold = sum(e[3] for e in sell_events if e[2] == "MELON")
    revenue_at_base = total_melons_sold * base_price
    price_decay_loss = revenue_at_base - total_revenue
    print(f"Total melons sold: {total_melons_sold}")
    print(f"Revenue at base price ($250/melon): ${revenue_at_base:,}")
    print(f"Actual revenue: ${total_revenue:,}")
    print(f"PRICE DECAY LOSS: ${price_decay_loss:,}")
    print(f"\nSell events by price:")
    for e in sell_events:
        print(f"  Step {e[0]:3d} Day {e[1]:2d} | {e[2]:6s} x{e[3]:3d} @ ${e[4]:3d} = ${e[5]:,}")
    
    # 2. EXCESSIVE HIRING COST
    print("\n--- 2. EXCESSIVE HIRING COST ---")
    total_hire_cost = sum(e[2] for e in hire_events)
    total_hires = len(hire_events)
    hires_by_day = {}
    for e in hire_events:
        d = e[1]
        hires_by_day[d] = hires_by_day.get(d, 0) + 1
    print(f"Total hires: {total_hires}")
    print(f"Total hire cost: ${total_hire_cost:,}")
    print(f"Hires per day: {dict(sorted(hires_by_day.items()))}")
    # Calculate cost with minimal hiring (2 workers/day)
    minimal_cost = 0
    for d in range(30):
        for h in range(min(2, hires_by_day.get(d, 0))):
            minimal_cost += fib(h)
    excess_hire_cost = total_hire_cost - minimal_cost
    print(f"Minimal hire cost (2/day): ${minimal_cost:,}")
    print(f"EXCESS HIRING COST: ${excess_hire_cost:,}")
    
    # 3. SEED SPENDING
    print("\n--- 3. SEED SPENDING ---")
    total_seed_cost = sum(e[5] for e in seed_events)
    seeds_by_crop = {}
    for e in seed_events:
        seeds_by_crop[e[2]] = seeds_by_crop.get(e[2], 0) + e[3]
    print(f"Total seeds purchased: {seeds_by_crop}")
    print(f"Total seed cost: ${total_seed_cost:,}")
    # How many of those seeds were planted vs wasted?
    planted_by_crop = {}
    for e in plant_events:
        planted_by_crop[e[2]] = planted_by_crop.get(e[2], 0) + 1
    print(f"Total seeds planted: {planted_by_crop}")
    wasted_seeds = {}
    for crop, bought in seeds_by_crop.items():
        planted = planted_by_crop.get(crop, 0)
        wasted = bought - planted
        if wasted > 0:
            wasted_seeds[crop] = wasted
    if wasted_seeds:
        wasted_cost = sum(CROP_DATA[c]["seed_cost"] * n for c, n in wasted_seeds.items())
        print(f"WASTED SEEDS (bought but never planted): {wasted_seeds}")
        print(f"WASTED SEED COST: ${wasted_cost:,}")
    else:
        print("No wasted seeds.")
    
    # 4. LATE PLANTING (melons planted too late to ever harvest)
    print("\n--- 4. LATE / UNHARVESTED PLANTING ---")
    print(f"Total plant actions: {len(plant_events)}")
    print(f"Total harvest actions: {len(harvest_events)}")
    melon_plants = [e for e in plant_events if e[2] == "MELON"]
    print(f"Melon plants: {len(melon_plants)}")
    print(f"Melon plants after Day 17 (cannot mature by Day 30): {len(late_melon_plants)}")
    for lp in late_melon_plants:
        print(f"  Step {lp[0]} Day {lp[1]}")
    wasted_late_seed_cost = len(late_melon_plants) * CROP_DATA["MELON"]["seed_cost"]
    print(f"WASTED LATE MELON SEED COST: ${wasted_late_seed_cost:,}")
    
    # 5. WORKER EFFICIENCY
    print("\n--- 5. WORKER ACTION EFFICIENCY ---")
    print(f"Total unit actions: {total_unit_actions}")
    print(f"  PASS: {total_pass_actions} ({100*total_pass_actions/total_unit_actions:.1f}%)")
    print(f"  MOVE: {total_move_actions} ({100*total_move_actions/total_unit_actions:.1f}%)")
    print(f"  WORK: {total_work_actions} ({100*total_work_actions/total_unit_actions:.1f}%)")
    move_waste = total_move_actions  # each move is 1 action not producing value
    print(f"Movement overhead: {total_move_actions} actions spent just traveling")
    
    # 6. TILE UTILIZATION
    print("\n--- 6. TILE UTILIZATION ---")
    print(f"Total unlocked tile-turns: {total_unlocked_tile_turns}")
    print(f"Occupied tile-turns: {total_occupied_tile_turns}")
    print(f"Empty tile-turns: {total_empty_tile_turns}")
    utilization = 100 * total_occupied_tile_turns / total_unlocked_tile_turns if total_unlocked_tile_turns else 0
    print(f"Utilization: {utilization:.1f}%")
    # Opportunity cost: each empty tile-turn that COULD have been growing melons
    # but approximating: 25 tiles * 288 turns (12 days) = 1 melon cycle
    
    # 7. LAND PURCHASE COST
    print("\n--- 7. LAND PURCHASE COST ---")
    total_land_cost = sum(e[2] for e in land_events)
    print(f"Total land cost: ${total_land_cost:,}")
    for e in land_events:
        print(f"  Step {e[0]} Day {e[1]} Cost ${e[2]:,} Money Before ${e[3]:,.0f}")

    # === SUMMARY ===
    print("\n" + "=" * 70)
    print("SUMMARY OF PROFIT LOSSES (RANKED BY ESTIMATED IMPACT)")
    print("=" * 70)
    print(f"Final Score: ${final_reward:,.0f}")
    print(f"Total Revenue from Sales: ${total_revenue:,}")
    print(f"Total Costs:")
    print(f"  Seeds: ${total_seed_cost:,}")
    print(f"  Hires: ${total_hire_cost:,}")
    print(f"  Land:  ${total_land_cost:,}")
    print(f"  Starting Money: $3,000")
    print(f"  Implied Final Money: $3,000 + ${total_revenue:,} - ${total_seed_cost:,} - ${total_hire_cost:,} - ${total_land_cost:,} = ${3000 + total_revenue - total_seed_cost - total_hire_cost - total_land_cost:,}")
    print(f"  Actual Final Money: ${final_reward:,.0f}")

run()
