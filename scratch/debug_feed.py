import sys, os
sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser
from run_k3 import Policy_K3

def debug():
    env = make("kaggriculture", debug=True, configuration={"episodeSteps": 721, "seed": 42})
    trainer = env.train([None, "scratch/agent_pass.py"])
    obs = trainer.reset()
    
    # We will buy an animal, place it, buy wheat, pickup wheat, move to animal, and feed.
    actions = [
        {"market": ["BUY_ANIMAL", "COW", 1]},
        {"market": ["BUY_PRODUCT", "WHEAT", 1]},
        {"farmer": ["BUILD_PASTURE"]}, # at 4,4? No, Shed is at 4,4, locked.
    ]
    
    # Let's just run run_k3's evaluator for B for 50 steps and print tasks and actions and fed_today!
    from run_k3 import K3Coordinator
    agent = K3Coordinator(1, 1, 1, "B")
    for step in range(50):
        action = agent(obs)
        obs, r, d, i = trainer.step(action)
        state = ObservationParser.parse(obs)
        worker = state.my_farm.farmer
        hungry = [t for row in state.my_farm.tiles for t in row if t.is_animal() and not t.fed_today]
        if worker.inventory.items.get("WHEAT", 0) > 0:
            print(f"Step {step} - Worker pos: {worker.position}, has wheat! Hungry animals: {[ (t.x, t.y, t.animal) for t in hungry ]}")
            print(f"  Action taken: {action['farmer']}")
        
        if any(t.fed_today for row in state.my_farm.tiles for t in row if t.is_animal()):
            print(f"Step {step} - ANIMAL FED TODAY!")
            
debug()
