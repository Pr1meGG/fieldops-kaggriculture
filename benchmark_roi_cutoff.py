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
    
    metrics = {
        "harvests": 0,
        "planted": 0,
        "seed_money_wasted": 0,
        "seed_purchases": defaultdict(int),
    }
    
    last_tiles = []
    unused_seeds = 0
    
    def wrapper(obs, cfg=None):
        nonlocal unused_seeds, last_tiles
        if not isinstance(obs, dict): return new_agent(obs)
        s = obs.get("step", 0)
        
        state = ObservationParser.parse(obs)
        my_farm = state.my_farm
        
        actions = new_agent(obs)
        
        # Telemetry from actions
        for act in [actions.get("farmer", ["PASS"])] + actions.get("hands", []):
            if not act: continue
            a = act[0]
            if a == "HARVEST": metrics["harvests"] += 1
            if a == "PLANT": metrics["planted"] += 1
                
        for ma in actions.get("market", []):
            if ma[0] == "BUY_SEED":
                crop = ma[1]
                qty = ma[2]
                metrics["seed_purchases"][crop] += qty
                
        if s == 718:
            last_tiles = []
            for y, row in enumerate(my_farm.tiles):
                for x, tile in enumerate(row):
                    if tile.kind == "PLANT":
                        last_tiles.append((tile.planted_day, tile.crop))
            unused_seeds = sum(my_farm.seeds.values()) if my_farm.seeds else 0
                        
        return actions

    steps = env.run([wrapper, "pass"])
    reward = steps[-1][0].reward
    
    # Calculate never harvested & wasted seed money
    never_harvested = len(last_tiles)
    seed_wasted = 0
    for planted_day, crop in last_tiles:
        if crop in CROP_DATA:
            seed_wasted += CROP_DATA[crop]["seed_cost"]

    return {
        "reward": reward,
        "harvests": metrics["harvests"],
        "planted": metrics["planted"],
        "never_harvested": never_harvested,
        "seed_wasted": seed_wasted,
        "seed_purchases": dict(metrics["seed_purchases"]),
        "unused_seeds": unused_seeds
    }

def main():
    num_sims = 100
    print("="*80)
    print("VALIDATION BENCHMARK: END-GAME ROI CUTOFF")
    print(f"{num_sims} simulations, seeds 42–{42+num_sims-1}")
    print("="*80)
    
    results = []
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        results = pool.map(run_simulation, range(42, 42+num_sims))
        
    rewards = [r['reward'] for r in results]
    mean_reward = statistics.mean(rewards)
    median_reward = statistics.median(rewards)
    std_reward = statistics.stdev(rewards) if len(rewards) > 1 else 0
    worst_reward = min(rewards)
    worst_seed = 42 + rewards.index(worst_reward)
    best_reward = max(rewards)
    best_seed = 42 + rewards.index(best_reward)
    
    # Baseline for submission-day2-v1 is ~37491 average.
    # For win rate, we'll just check how many seeds beat 37491 since we don't have seed-by-seed baseline.
    win_rate = sum(1 for r in rewards if r > 37491) / num_sims * 100
    
    print(f"\nResults for End-Game ROI Cutoff Agent:")
    print(f"Mean Reward:             ${mean_reward:,.0f}")
    print(f"Median Reward:           ${median_reward:,.0f}")
    print(f"Std Deviation:           ${std_reward:,.0f}")
    print(f"Win Rate (> 37.5k):      {win_rate:.1f}%")
    print(f"Worst Seed:              {worst_seed} (${worst_reward:,.0f})")
    print(f"Best Seed:               {best_seed} (${best_reward:,.0f})")
    print(f"Harvest Count:           {statistics.mean(r['harvests'] for r in results):.1f}")
    print(f"Planted Count:           {statistics.mean(r['planted'] for r in results):.1f}")
    print(f"Never Harvested Crops:   {statistics.mean(r['never_harvested'] for r in results):.1f}")
    print(f"Seed Money Wasted:       ${statistics.mean(r['seed_wasted'] for r in results):.0f}")
    print(f"Unused End-Game Seeds:   {statistics.mean(r['unused_seeds'] for r in results):.1f}")
    
    all_purchases = defaultdict(list)
    for r in results:
        for c, q in r['seed_purchases'].items():
            all_purchases[c].append(q)
            
    print("\nAverage Seed Purchases by Crop:")
    for crop in CROP_DATA.keys():
        avg = sum(all_purchases[crop]) / num_sims if crop in all_purchases else 0
        if avg > 0:
            print(f"  {crop}: {avg:.1f}")
            
    # Auto-revert criteria
    BASELINE = 37491
    print("\n" + "="*80)
    if mean_reward > BASELINE:
        print(f"SUCCESS: Reward increased from baseline (${BASELINE:,}) -> (${mean_reward:,.0f})")
    else:
        print(f"FAILURE: Reward (${mean_reward:,.0f}) did not beat baseline (${BASELINE:,})")
        print("REVERTING CODE CHANGES...")
        os.system("git restore src/fieldops/agent.py")
        print("Revert complete.")

if __name__ == "__main__":
    main()
