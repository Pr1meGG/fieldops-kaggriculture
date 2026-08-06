import sys
import os
sys.path.insert(0, os.path.abspath("src"))

from kaggle_environments import make
from fieldops.state import ObservationParser

def run_diagnostics():
    env = make("kaggriculture", debug=True)
    steps = env.run(["src/fieldops/agent.py", "pass"])

    total_tiles_planted = 0
    total_unlocked_tiles_across_turns = 0
    total_occupied_tiles_across_turns = 0
    worker_total_action_opportunities = 0
    worker_idle_actions = 0
    seeds_purchased_by_crop = {}
    revenue_per_crop = {}
    money_spent_on_workers = 0
    money_spent_on_land = 0
    turns_no_useful_action = 0
    land_purchases = []
    hires_timeline = []

    for i, step in enumerate(steps):
        obs_dict = step[0].observation
        if obs_dict.get('step') is None or obs_dict.get('step') >= 719:
            continue

        state = ObservationParser.parse(obs_dict)
        my_farm = state.my_farm

        unlocked_tiles_count = len(my_farm.unlocked_quadrants) * 25
        total_unlocked_tiles_across_turns += unlocked_tiles_count

        occupied = sum(1 for row in my_farm.tiles for t in row if t.kind is not None and t.kind != "LOCKED")
        total_occupied_tiles_across_turns += occupied

        action = step[0].action

        if action:
            market_acts = action.get("market", [])
            for m in market_acts:
                if not m: continue
                op = m[0]
                if op == "BUY_SEED":
                    crop = m[1]
                    cnt = m[2]
                    seeds_purchased_by_crop[crop] = seeds_purchased_by_crop.get(crop, 0) + cnt
                elif op == "HIRE":
                    money_spent_on_workers += 1
                    hires_timeline.append(state.day)
                elif op == "BUY_LAND":
                    tier = len(my_farm.unlocked_quadrants)
                    cost = 1000 if tier == 1 else (2000 if tier == 2 else 4000)
                    money_spent_on_land += cost
                    land_purchases.append((state.day, my_farm.unlocked_quadrants))
                elif op == "SELL":
                    crop = m[1]
                    cnt = m[2]
                    price = state.market.prices.get(crop, 0)
                    revenue_per_crop[crop] = revenue_per_crop.get(crop, 0) + (cnt * price)

            unit_acts = [action.get("farmer", ["PASS"])] + action.get("hands", [])
            
            for act in unit_acts:
                worker_total_action_opportunities += 1
                if act == ["PASS"]:
                    worker_idle_actions += 1
                elif act and act[0] == "PLANT":
                    total_tiles_planted += 1

            if all(a == ["PASS"] for a in unit_acts) and not market_acts:
                turns_no_useful_action += 1

    final_money = steps[-1][0].observation['farms'][0]['money']
    final_reward = steps[-1][0].reward

    avg_utilization = (total_occupied_tiles_across_turns / total_unlocked_tiles_across_turns) * 100
    worker_idle_pct = (worker_idle_actions / worker_total_action_opportunities) * 100 if worker_total_action_opportunities else 0

    print("=== STAGE 1 QUANTITATIVE BENCHMARK ===")
    print(f"1. Total tiles planted: {total_tiles_planted}")
    print(f"2. Average utilization of unlocked farmland: {avg_utilization:.2f}%")
    print(f"3. Worker idle percentage: {worker_idle_pct:.2f}% ({worker_idle_actions}/{worker_total_action_opportunities} actions)")
    print(f"4. Seeds purchased by crop: {seeds_purchased_by_crop}")
    print(f"5. Revenue per crop: {revenue_per_crop}")
    print(f"6. Money spent on workers: ${money_spent_on_workers}")
    print(f"7. Money spent on land: ${money_spent_on_land}")
    print(f"8. Land purchase timeline: {land_purchases}")
    print(f"9. Turns where no useful action performed: {turns_no_useful_action} / 719 turns")
    print(f"10. FINAL SCORE: ${final_reward:,.2f} (vs $20,551.00 baseline)")
    print("======================================")

if __name__ == "__main__":
    run_diagnostics()
