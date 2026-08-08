import sys
import os
import multiprocessing
import pandas as pd

sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser, Position
from fieldops.constants import ANIMAL_DATA
from fieldops.agent import MiniMelonAgent

# -------------------------------------------------------------
# We must build a subclass that adds Livestock routing
# because the base Champion only routes for Plants.
# -------------------------------------------------------------
def _distance(p1, p2):
    return abs(p1.x - p2.x) + abs(p1.y - p2.y)
    
def _choose_movement(current, target):
    dx = target.x - current.x
    dy = target.y - current.y
    if abs(dx) > abs(dy): return "EAST" if dx > 0 else "WEST"
    elif dy != 0: return "SOUTH" if dy > 0 else "NORTH"
    elif dx != 0: return "EAST" if dx > 0 else "WEST"
    return "PASS"

def create_livestock_agent(animal_type):
    class LivestockAgent(MiniMelonAgent):
        def __init__(self):
            super().__init__()
            self.target_animals = 5 if animal_type else 0
            
        def __call__(self, obs: dict) -> dict:
            if not isinstance(obs, dict): return super().__call__(obs)
            state = ObservationParser.parse(obs)
            my_farm = state.my_farm
            
            # Run base logic to get baseline allocations
            actions = super().__call__(obs)
            
            if not animal_type:
                return actions # Control agent
                
            # Market Logic for Animals
            animals_owned = sum(1 for row in my_farm.tiles for t in row if getattr(t, 'animal', None) == animal_type)
            
            if animals_owned < self.target_animals and state.day < 15:
                cost = ANIMAL_DATA[animal_type]["purchase_cost"]
                if my_farm.money > cost + 500: # maintain buffer
                    actions["market"].append(["BUY_LIVESTOCK", animal_type, 1])
                    
            # ---------------------------------------------------
            # Custom Priority Routing for Animals
            # (Insert ahead of Drop/Plant, behind Plant-Water)
            # ---------------------------------------------------
            unfed_animals = []
            harvestable_animals = []
            
            for y, row in enumerate(my_farm.tiles):
                for x, tile in enumerate(row):
                    if getattr(tile, 'animal', None) is not None:
                        pos = Position(x=x, y=y)
                        
                        # Is it fed today?
                        if not getattr(tile, 'fed_today', True):
                            unfed_animals.append(pos)
                            
                        # Is it harvestable?
                        # This depends on first_yield_day and yield_interval
                        # We approximate by checking if there's product
                        if getattr(tile, 'has_product', False):
                            harvestable_animals.append(pos)
                            
            # We override the worker actions from the base agent if there are animal tasks
            all_units = [my_farm.farmer] + list(my_farm.hands)
            base_unit_actions = [actions.get("farmer", ["PASS"])] + actions.get("hands", [])
            new_unit_actions = []
            
            targeted_tiles = set()
            
            for i, unit in enumerate(all_units):
                base_act = base_unit_actions[i]
                
                # If they are doing something crucial (WATER/HARVEST plant), let them
                if base_act[0] in ["WATER", "HARVEST"]:
                    new_unit_actions.append(base_act)
                    # We can't know exactly what they targeted, so we just append it
                    continue
                    
                # Priority: Harvest Animal
                valid_harvest = [p for p in harvestable_animals if p not in targeted_tiles]
                if valid_harvest:
                    target = min(valid_harvest, key=lambda p: _distance(unit.position, p))
                    targeted_tiles.add(target)
                    if unit.position == target:
                        new_unit_actions.append(["HARVEST"]) # Harvest animal product
                    else:
                        new_unit_actions.append([_choose_movement(unit.position, target)])
                    continue
                    
                # Priority: Feed Animal
                valid_feed = [p for p in unfed_animals if p not in targeted_tiles]
                if valid_feed:
                    # Feeding requires Wheat! We assume Wheat is in shed
                    has_feed = my_farm.shed.get("WHEAT", 0) > 0
                    if has_feed:
                        target = min(valid_feed, key=lambda p: _distance(unit.position, p))
                        targeted_tiles.add(target)
                        if unit.position == target:
                            new_unit_actions.append(["FEED"]) 
                        else:
                            new_unit_actions.append([_choose_movement(unit.position, target)])
                        continue
                        
                # Otherwise, stick to base action (DROP, PLANT, PASS)
                new_unit_actions.append(base_act)
                
            actions["farmer"] = new_unit_actions[0]
            actions["hands"] = new_unit_actions[1:]
            
            return actions
            
    return LivestockAgent()

def run_livestock_sweep(args):
    seed, animal_type = args
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    agent_inst = create_livestock_agent(animal_type)
    
    def wrapper(obs, config=None):
        if getattr(obs, 'step', 0) > 718: return agent_inst(obs)
        try:
            return agent_inst(obs)
        except Exception:
            return {"farmer": ["PASS"]}
            
    env.run([wrapper, "pass"])
    reward = env.steps[-1][0].reward or 0
    
    return {
        "seed": seed,
        "strategy": animal_type if animal_type else "CONTROL",
        "final_money": reward
    }

def main():
    seeds = list(range(1300, 1350)) # 50 seeds for speed
    strategies = [None, "COW", "SHEEP", "GOOSE"]
    
    print("EXP-012: Empirical Livestock Benchmark")
    print(f"Testing strategies: {strategies} over {len(seeds)} seeds...")
    
    tasks = [(s, a) for s in seeds for a in strategies]
    
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        results = pool.map(run_livestock_sweep, tasks)
        
    df = pd.DataFrame(results)
    
    print("\n=========================================================")
    print("Livestock Strategy Final Reward")
    print("=========================================================")
    
    summary = df.groupby("strategy")["final_money"].mean().reset_index()
    summary = summary.sort_values("final_money", ascending=False)
    
    for _, row in summary.iterrows():
        print(f"Strategy: {row['strategy']:>8} | Mean Reward: ${row['final_money']:,.2f}")

if __name__ == "__main__":
    main()
