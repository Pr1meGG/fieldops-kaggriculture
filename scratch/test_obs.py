import sys, os
from kaggle_environments import make

env = make("kaggriculture", debug=False, configuration={"episodeSteps": 10, "seed": 1})
trainer = env.train([None, "scratch/agent_pass.py"])
obs = trainer.reset()
print(type(obs))
if isinstance(obs, dict):
    print("Keys:", obs.keys())
    print("Step:", obs.get("step"))
