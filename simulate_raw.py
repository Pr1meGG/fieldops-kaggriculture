import sys
import os
sys.path.insert(0, os.path.abspath("src"))

from kaggle_environments import make
from fieldops.state import ObservationParser

def run_raw_evidence():
    env = make("kaggriculture", debug=True)
    steps = env.run(["src/fieldops/agent.py", "pass"])

    buy_land_log = []
    buy_seed_log = []
    sell_log = []
    harvest_counts = {}
    sold_counts = {}
    total_hires = 0
    total_planted = 0
    illegal_action_count = 0
    
    last_unlocked_quads = ["NW"]

    for i, step in enumerate(steps):
        obs_dict = step[0].observation
        status = step[0].status
        if status == "INVALID":
            illegal_action_count += 1

        if obs_dict.get('step') is None or obs_dict.get('step') >= 719:
            continue

        state = ObservationParser.parse(obs_dict)
        day = state.day
        hour = state.hour
        step_num = state.step
        my_farm = state.my_farm
        
        current_quads = my_farm.unlocked_quadrants
        if len(current_quads) > len(last_unlocked_quads):
            # Land purchase succeeded!
            last_unlocked_quads = list(current_quads)

        action = step[0].action
        if action:
            market_acts = action.get("market", [])
            for m in market_acts:
                if not m: continue
                op = m[0]
                if op == "BUY_LAND":
                    # Money before: my_farm.money
                    money_before = my_farm.money
                    # Money after will be captured on next turn, but cost is known
                    buy_land_log.append((day, step_num, money_before, current_quads))
                elif op == "BUY_SEED":
                    crop, qty = m[1], m[2]
                    buy_seed_log.append((crop, qty, day, step_num))
                elif op == "SELL":
                    crop, qty = m[1], m[2]
                    price = state.market.prices.get(crop, 0)
                    sell_log.append((crop, qty, price, day, step_num))
                    sold_counts[crop] = sold_counts.get(crop, 0) + qty
                elif op == "HIRE":
                    total_hires += 1

            unit_acts = [action.get("farmer", ["PASS"])] + action.get("hands", [])
            for act in unit_acts:
                if not act: continue
                if act[0] == "PLANT":
                    total_planted += 1
                elif act[0] == "HARVEST":
                    # Crop at position
                    # We track harvest counts in general
                    crop_type = act[1] if len(act) > 1 else "MELON" # Usually melon
                    harvest_counts[crop_type] = harvest_counts.get(crop_type, 0) + 1

    final_obs = steps[-1][0].observation
    final_reward = steps[-1][0].reward
    final_money = final_obs['farms'][0]['money']
    final_quads = final_obs['farms'][0]['unlocked_quadrants']

    print("==================================================")
    print("RAW SIMULATOR EVIDENCE REPORT")
    print("==================================================")
    print(f"1. Final Reward (direct from env.run): {final_reward}")
    print(f"2. Final Money (direct from obs): ${final_money:,.2f}")
    print(f"3. Unlocked Quadrants: {final_quads}")
    print(f"4. Total Land Owned: {len(final_quads) * 25} tiles")
    print(f"5. Total Planted Tiles: {total_planted}")
    print(f"6. Harvested Actions by Crop (approx): {harvest_counts}")
    print(f"7. Sold Units by Crop: {sold_counts}")
    print(f"8. Total Hires: {total_hires}")
    print(f"9. Total Land Purchases Executed: {len(buy_land_log)}")
    print(f"10. Illegal Actions Occurred: {illegal_action_count}")
    print("==================================================")
    
    print("\n--- BUY_LAND ACTIONS LOG ---")
    for item in buy_land_log:
        print(f"Day {item[0]:2d} | Step {item[1]:3d} | Money Before: ${item[2]:,.2f} | Quads at Turn: {item[3]}")

    print("\n--- BUY_SEED ACTIONS LOG (FIRST 20) ---")
    for item in buy_seed_log[:20]:
        print(f"Crop: {item[0]:5s} | Qty: {item[1]:2d} | Day: {item[2]:2d} | Step: {item[3]:3d}")
    print(f"... total BUY_SEED orders: {len(buy_seed_log)}")

    print("\n--- SELL ACTIONS LOG (FIRST 20) ---")
    for item in sell_log[:20]:
        print(f"Crop: {item[0]:5s} | Qty: {item[1]:3d} | Market Price: ${item[2]:3d} | Day: {item[3]:2d} | Step: {item[4]:3d}")
    print(f"... total SELL orders: {len(sell_log)}")

    print("\n--- LAST 100 STEPS ACTION LOG (Steps 620 to 719) ---")
    for i in range(620, min(720, len(steps))):
        s = steps[i][0]
        obs = s.observation
        step_idx = obs.get('step', i)
        day_idx = obs.get('day', i // 24)
        hour_idx = obs.get('hour', i % 24)
        act = s.action
        if act and (act.get("farmer") != ["PASS"] or act.get("hands") or act.get("market")):
            print(f"Step {step_idx:3d} (D{day_idx:02d}:H{hour_idx:02d}) -> {act}")

run_raw_evidence()
