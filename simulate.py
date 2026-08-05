import sys
import os
sys.path.insert(0, os.path.abspath("src"))

from kaggle_environments import make
from fieldops.state import ObservationParser

def run_analysis():
    env = make("kaggriculture", debug=True)
    steps = env.run(["src/fieldops/agent.py", "pass"])
    
    seeds_bought = 0
    hands_hired_by_day = {}
    tiles_planted = set()
    harvests = 0
    drops = 0
    sells = 0
    
    for i, step in enumerate(steps):
        obs_dict = step[0].observation
        if obs_dict.get('step') is None or obs_dict.get('step') >= 719: continue
        
        state = ObservationParser.parse(obs_dict)
        day = state.day
        
        action = step[0].action
        if not action: continue
        
        for act in action.get("market", []):
            if not act: continue
            if act[0] == "BUY_SEED" and act[1] == "MELON":
                seeds_bought += act[2]
            elif act[0] == "HIRE":
                hands_hired_by_day[day] = hands_hired_by_day.get(day, 0) + 1
            elif act[0] == "SELL" and act[1] == "MELON":
                sells += act[2]
                
        all_unit_actions = []
        if action.get("farmer"): all_unit_actions.append(action["farmer"])
        all_unit_actions.extend(action.get("hands", []))
        
        for act in all_unit_actions:
            if not act: continue
            if act[0] == "HARVEST":
                harvests += 1
            elif act[0] == "DROP":
                drops += 1
                
        for y, row in enumerate(state.my_farm.tiles):
            for x, tile in enumerate(row):
                if tile.kind == "PLANT" and tile.crop == "MELON":
                    tiles_planted.add((x, y))

    final_money = steps[-1][0].observation['farms'][0]['money']
    final_reward = steps[-1][0].reward

    print(f"Seeds bought: {seeds_bought}")
    print(f"Planted: {len(tiles_planted)}")
    print(f"Harvest actions: {harvests}")
    print(f"Drop actions: {drops}")
    print(f"Melons sold: {sells}")
    print(f"Final money: {final_money}")

run_analysis()
