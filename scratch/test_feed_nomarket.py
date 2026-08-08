import sys, os
sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser

def run():
    env = make("kaggriculture", debug=True, configuration={"episodeSteps": 721, "seed": 42})
    trainer = env.train([None, "random"])
    obs = trainer.reset()
    actions = [
        {"market": [["BUY_ANIMAL", "COW", 1], ["BUY_PRODUCT", "WHEAT", 10]], "farmer": ["BUILD_PASTURE"]},
        {"market": [], "farmer": ["SOUTH"]},
        {"market": [], "farmer": ["PICKUP", "COW"]},
        {"market": [], "farmer": ["NORTH"]},
        {"market": [], "farmer": ["PLACE", "COW"]},
        {"market": [], "farmer": ["SOUTH"]},
        {"market": [], "farmer": ["PICKUP", "WHEAT"]},
        {"market": [], "farmer": ["NORTH"]},
        {"market": [], "farmer": ["WEST"]},
        {"market": [], "farmer": ["WEST"]},
        {"market": [], "farmer": ["PASS"]},
    ]
    for i, a in enumerate(actions):
        obs, reward, done, info = trainer.step(a)
        state = ObservationParser.parse(obs)
        print(f"Step {i}: Action {a} -> Farmer inventory: {state.my_farm.farmer.inventory.items}, Shed: {state.my_farm.shed.items}")
    print("Done")

run()
