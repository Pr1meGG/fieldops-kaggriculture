import sys
import os
import multiprocessing
import statistics
from collections import defaultdict

sys.path.insert(0, os.path.abspath("src"))

from kaggle_environments import make
from fieldops.state import ObservationParser, Position
from fieldops.constants import CROP_DATA

# Import the new modified agent
from fieldops.agent import agent as new_agent

def run_simulation(seed):
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    
    # We need to wrap it to collect telemetry
    tile_history = defaultdict(list)
    metrics = {
        "harvests": 0,
        "planted": 0,
        "move_acts": 0,
        "prod_acts": 0,
        "total_watered": 0,
        "total_plant_turns": 0
    }
    
    def wrapper(obs, cfg=None):
        s = obs.get("step", 0) if isinstance(obs, dict) else getattr(obs, "step", 0)
        if s >= 719: return {"farmer": ["PASS"], "hands": [], "market": []}
        
        state = ObservationParser.parse(obs)
        my_farm = state.my_farm
        max_melon = CROP_DATA["MELON"]["max_yield_day"]
        max_carrot = CROP_DATA["CARROT"]["max_yield_day"]
        
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                pos = Position(x=x, y=y)
                quad = "NW" if x < 5 and y < 5 else ("NE" if x >= 5 and y < 5 else ("SW" if x < 5 and y >= 5 else "SE"))
                state_str = "LOCKED"
                if quad in my_farm.unlocked_quadrants:
                    if tile.is_empty():
                        state_str = "EMPTY"
                    elif tile.kind == "PLANT":
                        md = max_melon if tile.crop == "MELON" else max_carrot
                        if tile.planted_day is not None and (state.day - tile.planted_day) >= md:
                            state_str = "MATURE"
                        elif tile.watered_today:
                            state_str = "GROWING"
                        else:
                            state_str = "UNWATERED"
                            
                hist = tile_history[(x, y)]
                if not hist or hist[-1][0] != state_str:
                    hist.append((state_str, state.step))
                    
                if state_str == "GROWING":
                    metrics["total_watered"] += 1
                if state_str in ("GROWING", "UNWATERED", "MATURE"):
                    metrics["total_plant_turns"] += 1

        actions = new_agent(obs)
        
        # Telemetry from actions
        for act in [actions.get("farmer", ["PASS"])] + actions.get("hands", []):
            if not act: continue
            a = act[0]
            if a in ("NORTH", "SOUTH", "EAST", "WEST"):
                metrics["move_acts"] += 1
            elif a in ("WATER", "HARVEST", "PLANT", "DROP"):
                metrics["prod_acts"] += 1
                if a == "HARVEST": metrics["harvests"] += 1
                if a == "PLANT": metrics["planted"] += 1
                
        return actions

    steps = env.run([wrapper, "pass"])
    reward = steps[-1][0].reward
    
    # Calculate delays
    replant_delays = []
    empty_lifetimes = []
    for pos, hist in tile_history.items():
        for i in range(len(hist)-1):
            s1, t1 = hist[i]
            s2, t2 = hist[i+1]
            if s1 == "EMPTY" and s2 in ("UNWATERED", "GROWING"):
                empty_lifetimes.append(t2 - t1)
                # If it was MATURE right before EMPTY, it's a replant delay
                if i > 0 and hist[i-1][0] == "MATURE":
                    replant_delays.append(t2 - hist[i-1][1])

    move_pct = metrics["move_acts"] / max(1, (metrics["move_acts"] + metrics["prod_acts"])) * 100
    water_coverage = metrics["total_watered"] / max(1, metrics["total_plant_turns"]) * 100

    return {
        "reward": reward,
        "harvests": metrics["harvests"],
        "planted": metrics["planted"],
        "move_pct": move_pct,
        "water_coverage": water_coverage,
        "replant_delay": statistics.mean(replant_delays) if replant_delays else float('nan'),
        "empty_lifetime": statistics.mean(empty_lifetimes) if empty_lifetimes else float('nan'),
    }

def main():
    num_sims = 20
    print("="*80)
    print("BENCHMARKING GLOBAL DISTANCE SORT (ASSIGNMENT FIX)")
    print(f"{num_sims} simulations, seeds 42–{42+num_sims-1}")
    print("="*80)
    
    results = []
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        results = pool.map(run_simulation, range(42, 42+num_sims))
        
    print(f"\nResults for Global Distance Sort Agent:")
    print(f"Average Reward:        ${statistics.mean(r['reward'] for r in results):,.0f}")
    print(f"Movement %:            {statistics.mean(r['move_pct'] for r in results):.1f}%")
    
    rd = [r['replant_delay'] for r in results if r['replant_delay'] == r['replant_delay']]
    print(f"Harvest->Replant Dly:  {statistics.mean(rd) if rd else float('nan'):.1f} turns")
    
    el = [r['empty_lifetime'] for r in results if r['empty_lifetime'] == r['empty_lifetime']]
    print(f"Empty Tile Lifetime:   {statistics.mean(el) if el else float('nan'):.1f} turns")
    
    print(f"Harvest Count:         {statistics.mean(r['harvests'] for r in results):.1f}")
    print(f"Planted Count:         {statistics.mean(r['planted'] for r in results):.1f}")
    print(f"Water Coverage:        {statistics.mean(r['water_coverage'] for r in results):.1f}%")

if __name__ == "__main__":
    main()
