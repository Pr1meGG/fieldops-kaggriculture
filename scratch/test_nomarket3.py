import sys, os
sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser

def run():
    env = make("kaggriculture", debug=True, configuration={"episodeSteps": 721, "seed": 42})
    trainer = env.train([None, "random"])
    obs = trainer.reset()
    actions = [
        {"market": [["BUY_ANIMAL", "COW", 1], ["BUY_PRODUCT", "WHEAT", 10]], "farmer": ["NORTH"]},
        {"market": [], "farmer": ["NORTH"]},
        {"market": [], "farmer": ["NORTH"]},
        {"market": [], "farmer": ["NORTH"]},
        {"market": [], "farmer": ["WEST"]},
        {"market": [], "farmer": ["WEST"]},
        {"market": [], "farmer": ["WEST"]},
        {"market": [], "farmer": ["WEST"]},
        {"market": [], "farmer": ["BUILD_PASTURE"]},
        {"market": [], "farmer": ["SOUTH"]},
        {"market": [], "farmer": ["EAST"]},
        {"market": [], "farmer": ["SOUTH"]},
        {"market": [], "farmer": ["EAST"]},
        {"market": [], "farmer": ["SOUTH"]},
        {"market": [], "farmer": ["EAST"]},
        {"market": [], "farmer": ["SOUTH"]},
        {"market": [], "farmer": ["EAST"]},
        {"market": [], "farmer": ["PICKUP", "COW"]},
        {"market": [], "farmer": ["NORTH"]},
        {"market": [], "farmer": ["WEST"]},
        {"market": [], "farmer": ["NORTH"]},
        {"market": [], "farmer": ["WEST"]},
        {"market": [], "farmer": ["NORTH"]},
        {"market": [], "farmer": ["WEST"]},
        {"market": [], "farmer": ["NORTH"]},
        {"market": [], "farmer": ["WEST"]},
        {"market": [], "farmer": ["PLACE", "COW"]},
        {"market": [], "farmer": ["SOUTH"]},
        {"market": [], "farmer": ["EAST"]},
        {"market": [], "farmer": ["SOUTH"]},
        {"market": [], "farmer": ["EAST"]},
        {"market": [], "farmer": ["SOUTH"]},
        {"market": [], "farmer": ["EAST"]},
        {"market": [], "farmer": ["SOUTH"]},
        {"market": [], "farmer": ["EAST"]},
        {"market": [], "farmer": ["PICKUP", "WHEAT"]},
        {"market": [], "farmer": ["NORTH"]},
        {"market": [], "farmer": ["WEST"]},
        {"market": [], "farmer": ["NORTH"]},
        {"market": [], "farmer": ["WEST"]},
        {"market": [], "farmer": ["NORTH"]},
        {"market": [], "farmer": ["WEST"]},
        {"market": [], "farmer": ["NORTH"]},
        {"market": [], "farmer": ["WEST"]},
        {"market": [], "farmer": ["FEED"]},
        {"market": [], "farmer": ["PASS"]},
    ]
    for i, a in enumerate(actions):
        obs, reward, done, info = trainer.step(a)
        state = ObservationParser.parse(obs)
        farmer = state.my_farm.farmer
        print(f"Step {i:2d}: Farmer Pos: {farmer.position} | Inv: {farmer.inventory.items} | Action: {a['farmer']}")
        if i > 0 and len(farmer.inventory.items) == 0 and 'WHEAT' in actions[i-1]['farmer']:
            print("WHEAT DISAPPEARED")
    print("Done")

run()
