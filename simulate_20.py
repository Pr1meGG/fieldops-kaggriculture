import sys
import os
import math
import statistics
sys.path.insert(0, os.path.abspath("src"))

from kaggle_environments import make
from fieldops.state import ObservationParser

def run_20_simulations():
    rewards = []
    total_illegal_actions = 0
    total_crop_deaths = 0
    total_pass_actions = 0
    total_harvested_melons = 0
    successful_runs = 0

    print("Starting 20 independent simulation runs...")

    for seed_val in range(1, 21):
        try:
            env = make("kaggriculture", configuration={"seed": seed_val}, debug=True)
            steps = env.run(["src/fieldops/agent.py", "pass"])
            
            # Verify status
            final_step = steps[-1]
            if final_step[0].status == "DONE" or final_step[0].status == "ACTIVE":
                successful_runs += 1
            else:
                print(f"Run {seed_val} status: {final_step[0].status}")

            final_reward = final_step[0].reward
            rewards.append(final_reward)

            plant_tracker = set()
            harvested_in_run = 0

            for step in steps:
                obs_dict = step[0].observation
                if obs_dict.get('step') is None or obs_dict.get('step') >= 719:
                    continue

                state = ObservationParser.parse(obs_dict)
                action = step[0].action

                # Illegal actions check: status == "INVALID" or rejected
                if step[0].status == "INVALID":
                    total_illegal_actions += 1

                # Track actions
                if action:
                    farmer_act = action.get("farmer", ["PASS"])
                    hands_act = action.get("hands", [])

                    if farmer_act == ["PASS"]:
                        total_pass_actions += 1
                    elif farmer_act and farmer_act[0] == "HARVEST":
                        harvested_in_run += 1

                    for h in hands_act:
                        if h == ["PASS"]:
                            total_pass_actions += 1
                        elif h and h[0] == "HARVEST":
                            harvested_in_run += 1

                # Track plants to observe any crop deaths (turning into WEED)
                for y, row in enumerate(state.my_farm.tiles):
                    for x, tile in enumerate(row):
                        pos = (x, y)
                        if tile.kind == "PLANT" and tile.crop == "MELON":
                            plant_tracker.add(pos)
                        elif tile.kind == "WEED" and pos in plant_tracker:
                            total_crop_deaths += 1
                            plant_tracker.remove(pos)

            total_harvested_melons += harvested_in_run
            print(f"Run {seed_val:2d} | Seed: {seed_val:2d} | Reward: ${final_reward:,.2f} | Harvested: {harvested_in_run}")

        except Exception as e:
            print(f"Run {seed_val} failed with exception: {e}")

    mean_reward = statistics.mean(rewards)
    median_reward = statistics.median(rewards)
    best_reward = max(rewards)
    worst_reward = min(rewards)
    stdev_reward = statistics.stdev(rewards) if len(rewards) > 1 else 0.0

    print("\n" + "="*50)
    print("FINAL 20-RUN SIMULATION RESULTS")
    print("="*50)
    print(f"1. Mean reward:              ${mean_reward:,.2f}")
    print(f"2. Median reward:            ${median_reward:,.2f}")
    print(f"3. Best reward:              ${best_reward:,.2f}")
    print(f"4. Worst reward:             ${worst_reward:,.2f}")
    print(f"5. Standard deviation:       ${stdev_reward:,.2f}")
    print(f"6. Illegal actions:          {total_illegal_actions}")
    print(f"7. Crop deaths:              {total_crop_deaths}")
    print(f"8. Total PASS actions:       {total_pass_actions}")
    print(f"9. Harvested melons:         {total_harvested_melons}")
    print(f"10. Completed successfully:  {successful_runs} / 20")
    print("="*50)

if __name__ == "__main__":
    run_20_simulations()
