import sys
import os
import multiprocessing
import statistics

sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.agent import agent

def run_sim(seed):
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    
    # We simply pass the agent unmodified to prove the submission code is self-sufficient
    steps = env.run([agent, "pass"])
    
    reward = 0
    weeds = 0
    money = 0
    hands = 0
    plants = 0
    
    if steps and steps[-1] and steps[-1][0]:
        reward = steps[-1][0].reward
        obs = steps[-1][0].observation
        if isinstance(obs, dict) and "farms" in obs:
            my_farm = obs["farms"][0]
            money = my_farm["money"]
            hands = len(my_farm.get("hands", []))
            
            if "tiles" in my_farm:
                for row in my_farm["tiles"]:
                    for tile in row:
                        if isinstance(tile, dict):
                            if tile.get("kind") == "WEED": weeds += 1
                            if tile.get("kind") == "PLANT": plants += 1
                            
    return {"seed": seed, "reward": reward, "hands": hands, "plants": plants}

def main():
    seeds = list(range(100, 105)) # Just 5 seeds for a compact check
    with multiprocessing.Pool(processes=5) as pool:
        results = pool.map(run_sim, seeds)
        
    rewards = [r["reward"] for r in results]
    mean_reward = statistics.mean(rewards)
    
    print(f"Mean Reward: ${mean_reward:.2f}")
    print(f"Min Reward: ${min(rewards):.2f}")
    print(f"Max Reward: ${max(rewards):.2f}")
    print("Per-Seed Results:")
    for r in results:
        print(f"  Seed {r['seed']}: Reward=${r['reward']:.2f}, Hands={r['hands']}, Final Plants={r['plants']}")

if __name__ == "__main__":
    main()
