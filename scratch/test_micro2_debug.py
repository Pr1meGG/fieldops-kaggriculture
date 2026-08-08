import sys, os
sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from run_k2 import K2Coordinator, PolicyB_LocalFirstLivestock
from fieldops.state import ObservationParser

def run():
    env = make("kaggriculture", debug=True, configuration={"episodeSteps": 721, "seed": 42})
    trainer = env.train([None, "random"])
    agent = K2Coordinator(PolicyB_LocalFirstLivestock, 1, 1, 0)
    obs = trainer.reset()
    
    for i in range(55):
        action = agent(obs)
        obs, reward, done, info = trainer.step(action)
        state = ObservationParser.parse(obs)
        
        cow_fed = False
        for row in state.my_farm.tiles:
            for t in row:
                if t.kind == "PASTURE" and t.animal == "COW":
                    cow_fed = t.fed_today
                    
        print(f"Step {i:2d}")
        print(f"  Actions: Farmer={action['farmer']}, Hands={action.get('hands', [])}")
        print(f"  Cash: ${state.my_farm.money} | Farmer Pos: {state.my_farm.farmer.position} | Farmer Inv: {state.my_farm.farmer.inventory.items} | Hand Inv: {[h.inventory.items for h in state.my_farm.hands]}")
        print(f"  Shed Wheat: {state.my_farm.shed.items.get('WHEAT', 0)} | Fed: {cow_fed}")
        
        if cow_fed:
            print("SUCCESS")
            return

run()
