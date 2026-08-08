import sys, os
sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from run_k2 import K2Coordinator, PolicyB_LocalFirstLivestock
from fieldops.state import ObservationParser

def run():
    env = make("kaggriculture", debug=True, configuration={"episodeSteps": 721, "seed": 42})
    trainer = env.train([None, "scratch/agent_pass.py"])
    # 1 worker, 1 cow, 0 sheep
    agent = K2Coordinator(PolicyB_LocalFirstLivestock, 1, 1, 0)
    obs = trainer.reset()
    
    print("Running Micro-Test 2...")
    for i in range(75):
        action = agent(obs)
        obs, reward, done, info = trainer.step(action)
        state = ObservationParser.parse(obs)
        
        wheat_in_shed = state.my_farm.shed.items.get("WHEAT", 0)
        worker_inv = state.my_farm.farmer.inventory.items
        
        cow_fed = False
        for row in state.my_farm.tiles:
            for t in row:
                if t.kind == "PASTURE" and t.animal == "COW":
                    if t.fed_today:
                        cow_fed = True
                        
        print(f"Step {i:2d} | Action: {action['farmer']} | Shed Wheat: {wheat_in_shed} | Inv: {worker_inv} | Fed: {cow_fed}")
        
        if cow_fed:
            print("SUCCESS: Cow was fed!")
            return
            
    print("FAILED: Cow never fed.")
    sys.exit(1)

run()
