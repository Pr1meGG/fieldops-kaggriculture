import pytest
from kaggle_environments import make

def test_stage1_aggressive_expansion_agent():
    """
    Test Stage 1 Aggressive Expansion Agent:
    - Continuous production cycles (multiple melon/carrot harvests)
    - Dynamic land expansion (unlocks additional quadrants)
    - High profit (> $30,000)
    """
    env = make("kaggriculture", debug=True)
    steps = env.run(["src/fieldops/agent.py", "pass"])
    
    final_reward = steps[-1][0].reward
    assert final_reward is not None, "Episode should finish with a reward."
    assert final_reward > 30000, f"Expected reward > $30,000, but got {final_reward}"
    
    bought_seeds = False
    total_melons_sold = 0
    hired_hand = False
    watered_on_day_0 = False
    bought_land = False
    
    for step in steps:
        obs = step[0].observation
        my_action = step[0].action
        
        if not my_action:
            continue
            
        day = obs.get("day", 0)
        farmer_act = my_action.get("farmer", [])
        hands_act = my_action.get("hands", [])
        
        if day == 0:
            if farmer_act == ["WATER"] or any(h == ["WATER"] for h in hands_act):
                watered_on_day_0 = True
                
        market_actions = my_action.get("market", [])
        for action in market_actions:
            if not action:
                continue
            op = action[0]
            if op == "BUY_SEED" and action[1] == "MELON":
                bought_seeds = True
            elif op == "SELL" and action[1] == "MELON":
                total_melons_sold += action[2]
            elif op == "HIRE":
                hired_hand = True
            elif op == "BUY_LAND":
                bought_land = True
                
    assert bought_seeds, "Agent should buy melon seeds."
    assert hired_hand, "Agent should hire hands to scale workforce."
    assert watered_on_day_0, "Agent should water planted melons on Day 0 immediately."
    assert bought_land, "Agent should dynamically expand land when profitable."
    assert total_melons_sold >= 144, f"Expected >= 144 melons sold across multiple cycles, but got {total_melons_sold}"
