import sys
import os
import multiprocessing
import statistics
import json
import importlib
from collections import defaultdict

sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser
from fieldops.constants import CROP_DATA

def create_phase3_agent(is_champion=False, strategy_name="100_MELON"):
    import fieldops.agent
    importlib.reload(fieldops.agent)
    from fieldops.agent import MiniMelonAgent

    class Phase3BSweepAgent(MiniMelonAgent):
        def __call__(self, obs: dict) -> dict:
            if not isinstance(obs, dict): return super().__call__(obs)
            
            state = ObservationParser.parse(obs)
            my_farm = state.my_farm
            
            if is_champion:
                return super().__call__(obs)

            # --- Strategy Parser ---
            target_crops = ["MELON"]
            target_ratios = [1.0]
            
            if strategy_name == "100_MELON":
                target_crops = ["MELON"]
                target_ratios = [1.0]
            elif strategy_name == "90_MELON_10_WHEAT":
                target_crops = ["MELON", "WHEAT"]
                target_ratios = [0.9, 0.1]
            elif strategy_name == "80_MELON_20_WHEAT":
                target_crops = ["MELON", "WHEAT"]
                target_ratios = [0.8, 0.2]
            elif strategy_name == "WHEAT_UNTIL_EXP1":
                if len(my_farm.unlocked_quadrants) > 1:
                    target_crops = ["MELON"]
                else:
                    target_crops = ["WHEAT"]
            elif strategy_name == "WHEAT_UNTIL_CASH_5000":
                if my_farm.money > 5000:
                    target_crops = ["MELON"]
                else:
                    target_crops = ["WHEAT"]
            elif strategy_name == "WHEAT_UNTIL_DAY_10":
                if state.day >= 10:
                    target_crops = ["MELON"]
                else:
                    target_crops = ["WHEAT"]
            
            # Count existing crops on the field
            current_counts = defaultdict(int)
            total_plants = 0
            empty_tiles = 0
            for row in my_farm.tiles:
                for tile in row:
                    if tile.is_plant():
                        current_counts[tile.crop] += 1
                        total_plants += 1
                    elif tile.is_empty():
                        empty_tiles += 1

            # Determine the crop to plant next based on current ratios vs target ratios
            best_crop_to_plant = target_crops[0]
            if len(target_crops) > 1:
                greatest_deficit = -1.0
                for crop, ratio in zip(target_crops, target_ratios):
                    current_ratio = (current_counts[crop] / max(1, total_plants))
                    deficit = ratio - current_ratio
                    if deficit > greatest_deficit:
                        greatest_deficit = deficit
                        best_crop_to_plant = crop

            # We must override the BUY_SEED logic from MiniMelonAgent
            actions = super().__call__(obs)
            
            # Remove any BUY_SEED the base agent added
            actions["market"] = [a for a in actions["market"] if a[0] != "BUY_SEED"]
            
            # Add our own BUY_SEED logic
            if empty_tiles > 0:
                usable_seeds = my_farm.seeds.get(best_crop_to_plant, 0)
                if best_crop_to_plant == "MELON" and state.day + CROP_DATA["MELON"]["max_yield_day"] > 29:
                    pass # Too late to plant melon
                else:
                    target_buffer = min(empty_tiles, 8)
                    needed_seeds = target_buffer - usable_seeds
                    
                    if needed_seeds > 0:
                        seed_cost = CROP_DATA[best_crop_to_plant]["seed_cost"]
                        buy_qty = min(needed_seeds, int(my_farm.money // seed_cost))
                        if buy_qty > 0:
                            actions["market"].append(["BUY_SEED", best_crop_to_plant, buy_qty])
                            
            # Override planting logic to use the seeds we actually have
            # Base agent blindly plants MELON. We need to plant whatever seeds we have that match our strategy.
            # However, the base agent doesn't actually check seed types in the planting loop!
            # Let's fix that for the sweep agent.
            new_hands = []
            for act in actions.get("hands", []):
                if act[0] == "PLANT":
                    act[1] = best_crop_to_plant # Force it to plant our target crop
                new_hands.append(act)
            actions["hands"] = new_hands
            
            farmer_act = actions.get("farmer", ["PASS"])
            if farmer_act[0] == "PLANT":
                farmer_act[1] = best_crop_to_plant
            actions["farmer"] = farmer_act
            
            return actions

    return Phase3BSweepAgent()

def run_simulation(args):
    seed, is_champ, strategy = args
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    agent_instance = create_phase3_agent(is_champ, strategy)
    
    metrics = {
        "reward": 0,
        "harvest_count": 0,
        "worker_actions": {"MOVE": 0, "PRODUCTIVE": 0, "IDLE": 0},
        "water_backlog": [],
        "idle_tiles_count": 0,
        "crop_counts": defaultdict(int),
        "revenue_by_crop": defaultdict(int),
        "seed_cost_by_crop": defaultdict(int),
        "sell_prices_by_crop": defaultdict(list),
        "cash_reserve_over_time": [],
        "capital_in_land": 0
    }
    
    def wrapper(obs, cfg=None):
        if not isinstance(obs, dict): return agent_instance(obs)
        step = obs.get("step", 0)
        state = ObservationParser.parse(obs)
        my_farm = state.my_farm
        
        water_backlog = 0
        idle_tiles_this_turn = 0
        
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                if tile.is_plant():
                    if not tile.watered_today: water_backlog += 1
                if tile.is_empty():
                    idle_tiles_this_turn += 1
                    
        metrics["water_backlog"].append(water_backlog)
        metrics["idle_tiles_count"] += idle_tiles_this_turn
        
        if step % 24 == 0: 
            metrics["cash_reserve_over_time"].append(my_farm.money)
            metrics["capital_in_land"] = len(my_farm.unlocked_quadrants) * 1000 # Simplified metric
        
        actions = agent_instance(obs)
        
        # Track market events
        for ma in actions.get("market", []):
            if ma[0] == "SELL":
                item = ma[1]
                qty = ma[2]
                price = state.market.prices.get(item, 0)
                metrics["revenue_by_crop"][item] += price * qty
                metrics["sell_prices_by_crop"][item].append(price)
            elif ma[0] == "BUY_SEED":
                item = ma[1]
                qty = ma[2]
                cost = CROP_DATA.get(item, {}).get("seed_cost", 0)
                metrics["seed_cost_by_crop"][item] += cost * qty
        
        # Track worker events
        all_units = [my_farm.farmer] + list(my_farm.hands)
        unit_acts = [actions.get("farmer", ["PASS"])] + actions.get("hands", [])
        
        for unit, act in zip(all_units, unit_acts):
            if not act: continue
            a = act[0]
            
            if a in ["NORTH", "SOUTH", "EAST", "WEST"]: 
                metrics["worker_actions"]["MOVE"] += 1
            elif a == "PASS": 
                metrics["worker_actions"]["IDLE"] += 1
            else: 
                metrics["worker_actions"]["PRODUCTIVE"] += 1
                
            if a == "HARVEST":
                metrics["harvest_count"] += 1
            if a == "PLANT":
                crop = act[1] if len(act) > 1 else "MELON"
                metrics["crop_counts"][crop] += 1
            
        return actions

    steps = env.run([wrapper, "pass"])
    metrics["reward"] = steps[-1][0].reward
    
    total_actions = sum(metrics["worker_actions"].values())
    productive_pct = metrics["worker_actions"]["PRODUCTIVE"] / max(1, total_actions)
    avg_water_backlog = sum(metrics["water_backlog"])/len(metrics["water_backlog"]) if metrics["water_backlog"] else 0
    avg_idle_tiles_per_day = metrics["idle_tiles_count"] / 720
    
    return {
        "seed": seed,
        "reward": metrics["reward"],
        "harvest_count": metrics["harvest_count"],
        "productive_pct": productive_pct,
        "avg_water_backlog": avg_water_backlog,
        "avg_idle_tiles": avg_idle_tiles_per_day,
        "avg_cash_reserve": sum(metrics["cash_reserve_over_time"])/max(1, len(metrics["cash_reserve_over_time"])),
        "crop_counts": dict(metrics["crop_counts"]),
        "revenue": dict(metrics["revenue_by_crop"]),
        "seed_costs": dict(metrics["seed_cost_by_crop"]),
        "avg_sell_prices": {k: sum(v)/len(v) if v else 0 for k, v in metrics["sell_prices_by_crop"].items()}
    }

def main():
    seeds = list(range(300, 340)) # 40 seeds for Phase 3B parameter search
    
    strategies = [
        "100_MELON", 
        "90_MELON_10_WHEAT", 
        "80_MELON_20_WHEAT", 
        "WHEAT_UNTIL_EXP1",
        "WHEAT_UNTIL_CASH_5000",
        "WHEAT_UNTIL_DAY_10"
    ]
    
    print("Running Champion Baseline...")
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        champ_results = pool.map(run_simulation, [(s, True, "100_MELON") for s in seeds])
    champ_rewards = [r["reward"] for r in champ_results]
    champ_mean = statistics.mean(champ_rewards)
    
    results_by_param = {}
    print(f"\nChampion Mean Reward: ${champ_mean:.2f}\n")
    
    for strategy in strategies:
        print(f"Running Sweep: {strategy}...")
        args = [(s, False, strategy) for s in seeds]
        with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
            results = pool.map(run_simulation, args)
            
        rewards = [r["reward"] for r in results]
        mean_reward = statistics.mean(rewards)
        win_rate = sum(1 for c, t in zip(champ_rewards, rewards) if t > c) / len(seeds)
        
        # Aggregate complex metrics across all seeds
        agg_revenue = defaultdict(float)
        agg_profit = defaultdict(float)
        agg_sell_price = defaultdict(float)
        
        for r in results:
            for crop, rev in r["revenue"].items():
                agg_revenue[crop] += rev / len(seeds)
                agg_profit[crop] += (rev - r["seed_costs"].get(crop, 0)) / len(seeds)
            for crop, price in r["avg_sell_prices"].items():
                agg_sell_price[crop] += price / len(seeds)
        
        results_by_param[strategy] = {
            "reward": mean_reward,
            "delta_vs_champ": mean_reward - champ_mean,
            "win_rate": win_rate,
            "avg_idle_tiles": statistics.mean([r["avg_idle_tiles"] for r in results]),
            "revenue": dict(agg_revenue),
            "profit": dict(agg_profit),
            "avg_sell_price": dict(agg_sell_price),
            "productive_pct": statistics.mean([r["productive_pct"] for r in results]),
        }
        
        print(f"  {strategy:<25} -> Mean: ${mean_reward:<9.2f} | Delta: ${mean_reward - champ_mean:<9.2f} | Win Rate: {win_rate*100:.1f}%")

    with open("phase3b_sweep_results.json", "w") as f:
        json.dump(results_by_param, f, indent=2)
        
    print("\nPhase 3B Parameter Sweep complete.")

if __name__ == "__main__":
    main()
