import sys, os
sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser

def run():
    env = make("kaggriculture", debug=True, configuration={"episodeSteps": 721, "seed": 42})
    trainer = env.train([None, "random"])
    obs = trainer.reset()
    actions = [
        {"market": [["BUY_ANIMAL", "COW", 1]], "farmer": ["NORTH"]},
        {"market": [], "farmer": ["BUILD_PASTURE"]},
        {"market": [], "farmer": ["SOUTH"]},
        {"market": [], "farmer": ["PICKUP", "COW"]},
        {"market": [], "farmer": ["NORTH"]},
        {"market": [], "farmer": ["PLACE", "COW"]},
        {"market": [], "farmer": ["DROP"]},
        {"market": [], "farmer": ["PASS"]},
    ]
    for i, a in enumerate(actions):
        print(f"Step {i}: Action {a}")
        obs, reward, done, info = trainer.step(a)
        state = ObservationParser.parse(obs)
        farmer = state.my_farm.farmer
        print(f"  Farmer inventory: {farmer.inventory.items}")
        for row in state.my_farm.tiles:
            for t in row:
                if t.kind == "PASTURE":
                    print(f"  Pasture at ({t.x}, {t.y}) has animal: {t.animal}")
    print("Done")

run()
