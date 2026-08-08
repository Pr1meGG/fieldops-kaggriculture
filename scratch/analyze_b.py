import sys, os
sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from run_k2 import K2Coordinator, PolicyB_LocalFirstLivestock
from fieldops.state import ObservationParser

def run():
    env = make("kaggriculture", debug=True, configuration={"episodeSteps": 721, "seed": 42})
    trainer = env.train([None, "scratch/agent_pass.py"])
    agent = K2Coordinator(PolicyB_LocalFirstLivestock, 1, 1, 1) # 1 worker, 1 cow, 1 sheep
    obs = trainer.reset()
    
    metrics = {"fed_cow": 0, "milk": 0, "wool": 0, "melon": 0, "actions": {}}
    for i in range(718):
        action = agent(obs)
        farmer_act = action['farmer'][0]
        metrics["actions"][farmer_act] = metrics["actions"].get(farmer_act, 0) + 1
        
        obs, reward, done, info = trainer.step(action)
        state = ObservationParser.parse(obs)
        
        metrics["milk"] = max(metrics["milk"], state.my_farm.shed.items.get("MILK", 0))
        metrics["wool"] = max(metrics["wool"], state.my_farm.shed.items.get("WOOL", 0))
        
        for p in state.my_farm.shed.items:
            if p == "MELON": metrics["melon"] += 1
            
    print(f"Final Reward: {state.my_farm.money}")
    print(f"Metrics: {metrics}")

run()
