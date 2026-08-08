import sys
import os
sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make

def main():
    env = make("kaggriculture", debug=True, configuration={"episodeSteps": 5, "seed": 42})
    
    def test_agent(obs, config):
        step = obs.get("step", 0)
        farms = obs.get("farms", [{}])
        my_farm = farms[0] if farms else {}
        cash = my_farm.get("money", 0)
        hands = len(my_farm.get("hands", []))
        
        print(f"Step {step}: Cash=${cash}, Hands={hands}")
        
        # Try to hire 2 workers on step 0
        if step == 0:
            print("Action: HIRE x2")
            return {"market": [["HIRE"], ["HIRE"]]}
        elif step == 1:
            print("Action: MOVE EAST (Farmer), HIRE (Hand)")
            # Try to see if hand is available at step 1
            actions = {"farmer": ["EAST"]}
            if hands > 0:
                actions["hands"] = [["WEST"] * hands] # Not proper format maybe?
                # Actually, if there are hands, the format is a list of lists:
                actions["hands"] = [["WEST"] for _ in range(hands)]
            return actions
        
        return {}
        
    trainer = env.train([None, "pass"])
    obs = trainer.reset()
    for _ in range(4):
        act = test_agent(obs, env.configuration)
        obs, r, d, i = trainer.step(act)

if __name__ == "__main__":
    main()
