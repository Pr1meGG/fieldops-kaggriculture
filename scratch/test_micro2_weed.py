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
        if i == 46:
            print(f"Step {i}:")
            for row in state.my_farm.tiles:
                line = ""
                for t in row:
                    kind_str = t.kind if t.kind else "EMPTY"
                    has_f = "F" if state.my_farm.farmer.position.x == t.x and state.my_farm.farmer.position.y == t.y else ""
                    line += f"[{kind_str[:4]:4s}{has_f:1s}] "
                print(line)

run()
