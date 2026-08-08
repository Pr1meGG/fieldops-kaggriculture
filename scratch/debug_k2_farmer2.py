import sys, os
sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from run_k2 import K2Coordinator, PolicyB_LocalFirstLivestock

def run():
    env = make("kaggriculture", debug=True, configuration={"episodeSteps": 721, "seed": 42})
    trainer = env.train([None, "random"])
    agent = K2Coordinator(PolicyB_LocalFirstLivestock, 1, 1, 1)
    obs = trainer.reset()
    for i in range(24):
        action = agent(obs)
        print(f"Step {i}: Farmer {action['farmer']} | Hands {action['hands']} | Market {action['market']}")
        obs, reward, done, info = trainer.step(action)

run()
