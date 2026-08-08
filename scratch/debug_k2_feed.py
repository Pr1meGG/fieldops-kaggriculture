import sys, os
sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from run_k2 import K2Coordinator, PolicyB_LocalFirstLivestock
from fieldops.state import ObservationParser

def run():
    env = make("kaggriculture", debug=True, configuration={"episodeSteps": 721, "seed": 42})
    trainer = env.train([None, "random"])
    agent = K2Coordinator(PolicyB_LocalFirstLivestock, 1, 1, 1)
    obs = trainer.reset()
    for i in range(25):
        action = agent(obs)
        obs, reward, done, info = trainer.step(action)
        state = ObservationParser.parse(obs)
        my_farm = state.my_farm
        animals = []
        for row in my_farm.tiles:
            for t in row:
                if t.kind == "PASTURE":
                    animals.append((t.animal, getattr(t, "fed_today", False)))
        print(f"Step {i+1}: Animals in pastures: {animals}")

run()
