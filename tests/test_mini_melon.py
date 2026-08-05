import pytest
from kaggle_environments import make

def test_mini_melon_independent_scheduling_cycle():
    """
    Test that the Mini Melon Rush agent with independent per-unit task scheduling
    completes the cycle with 100% crop survival (all 12 plants harvested, 72 melons sold).
    """
    env = make("kaggriculture", debug=True)
    steps = env.run(["src/fieldops/agent.py", "pass"])
    
    final_reward = steps[-1][0].reward
    assert final_reward is not None, "Episode should finish with a reward."
    
    # We expect profit > 20000 with 72 melons harvested and sold
    assert final_reward > 20000, f"Expected profit > $20,000, but got {final_reward}"
    
    bought_seeds = False
    total_melons_sold = 0
    hired_hand = False
    watered_on_day_0 = False
    
    for step in steps:
        obs = step[0].observation
        my_action = step[0].action
        
        if not my_action:
            continue
            
        day = obs.get("day", 0)
        
        # Check unit actions on Day 0
        farmer_act = my_action.get("farmer", [])
        hands_act = my_action.get("hands", [])
        
        if day == 0:
            if farmer_act == ["WATER"] or any(h == ["WATER"] for h in hands_act):
                watered_on_day_0 = True
                
        # Check market actions
        market_actions = my_action.get("market", [])
        for action in market_actions:
            if not action:
                continue
            op = action[0]
            if op == "BUY_SEED" and action[1] == "MELON" and action[2] == 12:
                bought_seeds = True
            elif op == "SELL" and action[1] == "MELON":
                total_melons_sold += action[2]
            elif op == "HIRE":
                hired_hand = True
                
    assert bought_seeds, "Agent should have bought exactly 12 melon seeds."
    assert hired_hand, "Agent should have hired at least one hand."
    assert watered_on_day_0, "Agent should water planted melons on Day 0 immediately."
    assert total_melons_sold == 72, f"Expected 72 melons sold, but sold {total_melons_sold}"

