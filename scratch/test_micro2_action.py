import sys, os
sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from run_k2 import K2Coordinator, PolicyB_LocalFirstLivestock

def run():
    env = make("kaggriculture", debug=True, configuration={"episodeSteps": 721, "seed": 42})
    trainer = env.train([None, "scratch/agent_pass.py"])
    agent = K2Coordinator(PolicyB_LocalFirstLivestock, 1, 1, 0)
    obs = trainer.reset()
    
    for i in range(50):
        action = agent(obs)
        if i >= 45:
            print(f"Step {i}: Action {action}")
        obs, reward, done, info = trainer.step(action)

run()
