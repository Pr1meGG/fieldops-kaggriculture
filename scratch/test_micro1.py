import sys, os
sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from run_k2 import K2Coordinator, PolicyB_LocalFirstLivestock
from fieldops.state import ObservationParser

def run():
    env = make("kaggriculture", debug=True, configuration={"episodeSteps": 721, "seed": 42})
    trainer = env.train([None, "random"])
    # 1 worker, 1 cow, 0 sheep
    agent = K2Coordinator(PolicyB_LocalFirstLivestock, 1, 1, 0)
    obs = trainer.reset()
    
    print("Running Micro-Test 1...")
    for i in range(50):
        action = agent(obs)
        obs, reward, done, info = trainer.step(action)
        state = ObservationParser.parse(obs)
        
        cow_in_shed = state.my_farm.shed.items.get("COW", 0)
        worker_inv = state.my_farm.farmer.inventory.items
        
        pasture_cows = 0
        for row in state.my_farm.tiles:
            for t in row:
                if t.kind == "PASTURE" and t.animal == "COW":
                    pasture_cows += 1
                    
        print(f"Step {i:2d} | Action: {action['farmer']} | Shed: {cow_in_shed} | Inv: {worker_inv} | Pasture: {pasture_cows}")
        
        if pasture_cows > 0:
            print("SUCCESS: Cow placed in pasture!")
            return
            
    print("FAILED: Cow never reached pasture.")
    sys.exit(1)

run()
