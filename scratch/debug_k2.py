import sys, os
sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from run_k2 import K2Coordinator, PolicyB_LocalFirstLivestock

def run():
    env = make("kaggriculture", debug=True, configuration={"episodeSteps": 721, "seed": 42})
    trainer = env.train([None, "random"])
    agent = K2Coordinator(PolicyB_LocalFirstLivestock, 1, 0, 0)
    obs = trainer.reset()
    for _ in range(24):
        action = agent(obs)
        print("Market:", action["market"])
        obs, reward, done, info = trainer.step(action)
    farm = obs["farms"][0] if isinstance(obs, dict) else obs.farms[0]
    final_cash = farm.get("money", 0) if isinstance(farm, dict) else farm.money
    print("Money Day 1:", final_cash)

run()
