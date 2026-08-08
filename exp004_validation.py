import sys
import os
import multiprocessing
import statistics

sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser
from fieldops.constants import CROP_DATA

def create_exp004_agent(is_champion=False):
    import fieldops.agent
    import importlib
    importlib.reload(fieldops.agent)
    from fieldops.agent import MiniMelonAgent

    class Exp004Agent(MiniMelonAgent):
        def __call__(self, obs: dict) -> dict:
            if not isinstance(obs, dict): return super().__call__(obs)
            
            if is_champion:
                return super().__call__(obs)
                
            state = ObservationParser.parse(obs)
            my_farm = state.my_farm
            
            # Base agent logic
            actions = super().__call__(obs)
            
            # We must strip the base agent's BUY_SEED action because it used the flawed math
            actions["market"] = [a for a in actions["market"] if a[0] != "BUY_SEED"]
            
            # -------------------------------------------------------------
            # EXP-004: Corrected Seed Purchasing Arithmetic
            # -------------------------------------------------------------
            target_crop = "MELON"
            
            # Count empty tiles
            num_empty = 0
            for row in my_farm.tiles:
                for tile in row:
                    if tile.is_empty():
                        num_empty += 1
                        
            if num_empty > 0:
                # FIXED MATH: Strict key lookup, no double-counting loop
                usable_seeds = my_farm.seeds.get(target_crop, 0)
                
                # We still want to stop planting if it's too late in the game
                if state.day + CROP_DATA[target_crop]["max_yield_day"] > 29:
                    usable_seeds = 0 # Force 0 so we don't buy seeds we can't harvest
                    target_buffer = 0
                else:
                    target_buffer = min(num_empty, 8)
                
                needed_seeds = target_buffer - usable_seeds
                
                if needed_seeds > 0:
                    seed_cost = CROP_DATA[target_crop]["seed_cost"]
                    buy_qty = min(needed_seeds, int(my_farm.money // seed_cost))
                    if buy_qty > 0:
                        actions["market"].append(["BUY_SEED", target_crop, buy_qty])
                        
            return actions

    return Exp004Agent()

def run_simulation(args):
    seed, is_champ = args
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    agent_instance = create_exp004_agent(is_champ)
    
    metrics = {
        "reward": 0,
        "harvest_count": 0,
        "idle_tiles_count": 0,
    }
    
    def wrapper(obs, cfg=None):
        if not isinstance(obs, dict): return agent_instance(obs)
        state = ObservationParser.parse(obs)
        my_farm = state.my_farm
        
        idle_tiles_this_turn = sum(1 for row in my_farm.tiles for tile in row if tile.is_empty())
        metrics["idle_tiles_count"] += idle_tiles_this_turn
        
        actions = agent_instance(obs)
        
        all_units = [my_farm.farmer] + list(my_farm.hands)
        unit_acts = [actions.get("farmer", ["PASS"])] + actions.get("hands", [])
        for unit, act in zip(all_units, unit_acts):
            if act and act[0] == "HARVEST":
                metrics["harvest_count"] += 1
            
        return actions

    steps = env.run([wrapper, "pass"])
    metrics["reward"] = steps[-1][0].reward
    metrics["avg_idle_tiles"] = metrics["idle_tiles_count"] / 720
    
    return {
        "seed": seed,
        "reward": metrics["reward"],
        "harvest_count": metrics["harvest_count"],
        "avg_idle_tiles": metrics["avg_idle_tiles"]
    }

def main():
    seeds = list(range(400, 500)) # 100 paired seeds
    
    print("Running EXP-004: 100-Seed Validation (Champion V2 vs Seed Fix)...")
    
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        champ_results = pool.map(run_simulation, [(s, True) for s in seeds])
        
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        fix_results = pool.map(run_simulation, [(s, False) for s in seeds])
        
    champ_rewards = [r["reward"] for r in champ_results]
    fix_rewards = [r["reward"] for r in fix_results]
    
    champ_mean = statistics.mean(champ_rewards)
    fix_mean = statistics.mean(fix_rewards)
    
    champ_idle = statistics.mean([r["avg_idle_tiles"] for r in champ_results])
    fix_idle = statistics.mean([r["avg_idle_tiles"] for r in fix_results])
    
    wins = sum(1 for c, f in zip(champ_rewards, fix_rewards) if f > c)
    win_rate = wins / len(seeds)
    delta = fix_mean - champ_mean
    
    print(f"\nChampion V2 Mean: ${champ_mean:.2f} (Avg Idle Tiles: {champ_idle:.1f})")
    print(f"Seed Fix Mean:    ${fix_mean:.2f} (Avg Idle Tiles: {fix_idle:.1f})")
    print(f"Delta:            ${delta:+.2f}")
    print(f"Win Rate:         {win_rate*100:.1f}%\n")
    
    if delta > 0 and win_rate > 0.6:
        print("DECISION: PROMOTE")
    else:
        print("DECISION: REJECT")

if __name__ == "__main__":
    main()
