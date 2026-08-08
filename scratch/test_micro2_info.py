import sys, os
sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from run_k2 import K2Coordinator, PolicyB_LocalFirstLivestock
from fieldops.state import ObservationParser

def run():
    env = make("kaggriculture", debug=True, configuration={"episodeSteps": 721, "seed": 42})
    trainer = env.train([None, "scratch/agent_pass.py"])
    agent = K2Coordinator(PolicyB_LocalFirstLivestock, 1, 1, 0)
    obs = trainer.reset()
    
    for i in range(50):
        action = agent(obs)
        obs, reward, done, info = trainer.step(action)
        state = ObservationParser.parse(obs)
        
        if i >= 44:
            print(f"Step {i}: Action {action['farmer']} -> reward {reward}, info {info}, done {done}")
            print(f"  Farmer Pos: {state.my_farm.farmer.position} | Inv: {state.my_farm.farmer.inventory.items}")

run()
