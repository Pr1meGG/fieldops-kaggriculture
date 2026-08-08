import sys, os
sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from run_k2 import K2Coordinator, PolicyB_LocalFirstLivestock
from fieldops.state import ObservationParser
import pprint

def run():
    env = make("kaggriculture", debug=True, configuration={"episodeSteps": 721, "seed": 42})
    trainer = env.train([None, "random"])
    agent = K2Coordinator(PolicyB_LocalFirstLivestock, 1, 1, 1)
    obs = trainer.reset()
    for i in range(19):
        action = agent(obs)
        obs, reward, done, info = trainer.step(action)
    state = ObservationParser.parse(obs)
    print("Shed:", state.my_farm.shed.items)
    print("Seeds:", state.my_farm.seeds)

run()
