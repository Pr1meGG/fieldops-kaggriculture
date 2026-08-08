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
    
    metrics = {"fed_cow": 0, "fed_sheep": 0, "milk": 0, "wool": 0}
    for i in range(200):
        action = agent(obs)
        obs, reward, done, info = trainer.step(action)
        state = ObservationParser.parse(obs)
        
        milk_in_shed = state.my_farm.shed.items.get("MILK", 0)
        wool_in_shed = state.my_farm.shed.items.get("WOOL", 0)
        metrics["milk"] = max(metrics["milk"], milk_in_shed)
        metrics["wool"] = max(metrics["wool"], wool_in_shed)
        for row in state.my_farm.tiles:
            for t in row:
                if t.kind == "PASTURE":
                    if t.animal == "COW" and t.fed_today: metrics["fed_cow"] += 1
                    if t.animal == "SHEEP" and t.fed_today: metrics["fed_sheep"] += 1
                    
        if i % 50 == 0:
            print(f"Day {state.day} Hour {state.hour}: Cash: {state.my_farm.money} | Metrics: {metrics}")
            
    print(f"Final Day {state.day}: Cash: {state.my_farm.money} | Metrics: {metrics}")

run()
