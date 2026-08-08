import sys
import os

sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.agent import agent, _coordinator_instance
from fieldops.managers.worker_manager import V1WorkerManager

def main():
    print("Initializing environment...")
    env = make("kaggriculture", debug=True, configuration={"episodeSteps": 721, "seed": 42})
    
    _coordinator_instance.managers[2] = V1WorkerManager()
    
    # We want to find a state with a weed. Weeds spawn randomly over time.
    # Let's run a few days until a weed spawns.
    weed_found = False
    
    trainer = env.train([None, "pass"])
    obs = trainer.reset()
    
    for _ in range(718):
        # Find if weed exists
        weed_pos = None
        if isinstance(obs, dict) and "farms" in obs:
            for y, row in enumerate(obs["farms"][0]["tiles"]):
                for x, tile in enumerate(row):
                    if isinstance(tile, dict) and tile.get("kind") == "WEED":
                        weed_pos = (x, y)
                        break
                if weed_pos: break
        
        if weed_pos:
            print(f"Weed found at {weed_pos} on step {obs['step']}")
            weed_found = True
            
            # Step until weed is removed or 20 steps pass
            steps_taken = 0
            while steps_taken < 20:
                actions = agent(obs, env.configuration)
                print(f"Step {obs['step']} Actions: {actions}")
                obs, reward, done, info = trainer.step(actions)
                
                # Check if weed is still there
                weed_still_there = False
                if isinstance(obs, dict) and "farms" in obs:
                    tile = obs["farms"][0]["tiles"][weed_pos[1]][weed_pos[0]]
                    if isinstance(tile, dict) and tile.get("kind") == "WEED":
                        weed_still_there = True
                
                if not weed_still_there:
                    print(f"SUCCESS: Weed at {weed_pos} was removed at step {obs['step']}!")
                    break
                
                steps_taken += 1
                if done: break
                
            if weed_still_there:
                print(f"FAILURE: Weed at {weed_pos} was not removed after 20 steps.")
            
            break
            
        actions = agent(obs, env.configuration)
        obs, reward, done, info = trainer.step(actions)
        if done: break
        
    if not weed_found:
        print("No weed spawned in this seed. Try another.")

if __name__ == "__main__":
    main()
