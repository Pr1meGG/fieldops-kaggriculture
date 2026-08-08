import sys
import os
import multiprocessing
import statistics
import time

sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser
from fieldops.constants import CROP_DATA
from fieldops.agent import MiniMelonAgent

def create_control_agent():
    # The control agent injects the BUG back into the code
    class ControlAgent(MiniMelonAgent):
        def __call__(self, obs: dict) -> dict:
            if not isinstance(obs, dict): return super().__call__(obs)
            state = ObservationParser.parse(obs)
            my_farm = state.my_farm
            
            # Base agent logic
            actions = super().__call__(obs)
            
            # Revert the fix (re-inject the bug)
            # We strip the base agent's BUY_SEED action because it used the fixed math
            actions["market"] = [a for a in actions["market"] if a[0] != "BUY_SEED"]
            
            # -------------------------------------------------------------
            # The Buggy Logic
            # -------------------------------------------------------------
            empty_unlocked_tiles = [
                (x, y)
                for y, row in enumerate(my_farm.tiles)
                for x, tile in enumerate(row)
                if tile.is_empty()
            ]
            num_empty = len(empty_unlocked_tiles)
            
            best_crop = None
            best_profit = -1
            
            for crop_name, data in CROP_DATA.items():
                if state.day + data["max_yield_day"] <= 29:
                    profit = data["base_price"] * data["max_yield_unf"] - data["seed_cost"]
                    if profit > best_profit:
                        best_profit = profit
                        best_crop = crop_name
                        
            target_crop = best_crop
            
            if target_crop is not None and num_empty > 0:
                target_crop = "MELON" # <--- The Bug
                usable_seeds = my_farm.seeds.get(target_crop, 0)
            
                if state.day + CROP_DATA[target_crop]["max_yield_day"] > 29:
                    target_buffer = 0
                    usable_seeds = 0
                else:
                    target_buffer = min(num_empty, 8)
            
                needed_seeds = target_buffer - usable_seeds
                
                if needed_seeds > 0:
                    seed_cost = CROP_DATA[target_crop]["seed_cost"]
                    buy_qty = min(needed_seeds, int(my_farm.money // seed_cost))
                    if buy_qty > 0:
                        actions["market"].append(["BUY_SEED", target_crop, buy_qty])
                        
            return actions
    return ControlAgent()

def run_paired_benchmark(seed):
    control_env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    test_env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    
    control_agent = create_control_agent()
    test_agent = MiniMelonAgent() # This uses the freshly modified agent.py without the bug
    
    control_env.run([control_agent, "pass"])
    test_env.run([test_agent, "pass"])
    
    control_reward = control_env.steps[-1][0].reward or 0
    test_reward = test_env.steps[-1][0].reward or 0
    
    return {
        "seed": seed,
        "control": control_reward,
        "test": test_reward,
        "diff": test_reward - control_reward
    }

def main():
    seeds = list(range(1000, 1100))
    print("EXP-009: Late-Game Crop Hardcoding Bug Fix Paired Benchmark")
    print(f"Running {len(seeds)} paired seeds...")
    
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        results = pool.map(run_paired_benchmark, seeds)
        
    wins = 0
    losses = 0
    ties = 0
    diffs = []
    
    control_scores = []
    test_scores = []
    
    for r in results:
        diffs.append(r["diff"])
        control_scores.append(r["control"])
        test_scores.append(r["test"])
        
        if r["diff"] > 0:
            wins += 1
        elif r["diff"] < 0:
            losses += 1
        else:
            ties += 1
            
    mean_control = statistics.mean(control_scores)
    mean_test = statistics.mean(test_scores)
    mean_diff = statistics.mean(diffs)
    
    print("\n=========================================================")
    print("Benchmark Results (Across 100 Seeds)")
    print("=========================================================")
    print(f"Control (Champion V3) Mean Reward:    ${mean_control:,.2f}")
    print(f"Test    (Champion V4) Mean Reward:    ${mean_test:,.2f}")
    print(f"Mean Difference (Expected Value):     ${mean_diff:,.2f}")
    print(f"Win Rate:                             {wins/len(seeds):.1%}")
    print(f"Loss Rate:                            {losses/len(seeds):.1%}")
    print(f"Tie Rate:                             {ties/len(seeds):.1%}")
    print("=========================================================")
    
if __name__ == "__main__":
    main()
