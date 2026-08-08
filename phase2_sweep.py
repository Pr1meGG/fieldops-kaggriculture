import sys
import os
import multiprocessing
import statistics
import json
import importlib

sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser
from fieldops.constants import CROP_DATA

def create_phase2_agent(is_champion=False, utilization_threshold=100):
    import fieldops.agent
    importlib.reload(fieldops.agent)
    from fieldops.agent import MiniMelonAgent

    class Phase2SweepAgent(MiniMelonAgent):
        def __call__(self, obs: dict) -> dict:
            if not isinstance(obs, dict): return super().__call__(obs)
            
            state = ObservationParser.parse(obs)
            my_farm = state.my_farm
            
            actions = super().__call__(obs)
            
            if is_champion:
                return actions # Use the base champion logic
                
            # Replace Champion's BUY_LAND logic
            actions["market"] = [a for a in actions["market"] if a[0] != "BUY_LAND"]
            
            quads_unlocked = len(my_farm.unlocked_quadrants)
            if quads_unlocked < 4:
                total_tiles = quads_unlocked * 25
                planted_tiles = sum(1 for row in my_farm.tiles for tile in row if tile.is_plant())
                
                utilization_pct = (planted_tiles / total_tiles) * 100 if total_tiles > 0 else 100
                
                land_cost = 1000 if quads_unlocked == 1 else (2000 if quads_unlocked == 2 else 4000)
                seed_buffer = 25 * CROP_DATA["MELON"]["seed_cost"]
                worker_buffer = 100
                
                if utilization_pct >= utilization_threshold:
                    if my_farm.money >= (land_cost + seed_buffer + worker_buffer) and state.day <= 18:
                        actions["market"].append(["BUY_LAND"])
                
            return actions

    return Phase2SweepAgent()

def run_simulation(args):
    seed, is_champ, threshold = args
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    agent_instance = create_phase2_agent(is_champ, threshold)
    
    metrics = {
        "reward": 0,
        "harvest_count": 0,
        "worker_actions": {"MOVE": 0, "PRODUCTIVE": 0, "IDLE": 0},
        "water_backlog": [],
        "expansion_days": [],
        "expansion_money_at_unlock": [],
        "market_revenue": 0,
        "idle_tiles_count": 0,
        "plant_count_sum": 0,
        "cash_reserve_over_time": []
    }
    
    def wrapper(obs, cfg=None):
        if not isinstance(obs, dict): return agent_instance(obs)
        step = obs.get("step", 0)
        
        state = ObservationParser.parse(obs)
        my_farm = state.my_farm
        
        water_backlog = 0
        idle_tiles_this_turn = 0
        plant_this_turn = 0
        
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                if tile.is_plant():
                    plant_this_turn += 1
                    if not tile.watered_today:
                        water_backlog += 1
                if tile.is_empty():
                    idle_tiles_this_turn += 1
                    
        metrics["water_backlog"].append(water_backlog)
        metrics["idle_tiles_count"] += idle_tiles_this_turn
        metrics["plant_count_sum"] += plant_this_turn
        if step % 24 == 0:
            metrics["cash_reserve_over_time"].append(my_farm.money)
        
        actions = agent_instance(obs)
        
        for ma in actions.get("market", []):
            if ma[0] == "BUY_LAND":
                metrics["expansion_days"].append(state.day)
                metrics["expansion_money_at_unlock"].append(my_farm.money)
            elif ma[0] == "SELL":
                item = ma[1]
                qty = ma[2]
                price = state.market.prices.get(item, 0)
                metrics["market_revenue"] += price * qty
        
        all_units = [my_farm.farmer] + list(my_farm.hands)
        unit_acts = [actions.get("farmer", ["PASS"])] + actions.get("hands", [])
        
        for act in unit_acts:
            if not act: continue
            a = act[0]
            if a in ["NORTH", "SOUTH", "EAST", "WEST"]: 
                metrics["worker_actions"]["MOVE"] += 1
            elif a == "PASS": 
                metrics["worker_actions"]["IDLE"] += 1
            else: 
                metrics["worker_actions"]["PRODUCTIVE"] += 1
                
            if a == "HARVEST": metrics["harvest_count"] += 1
            
        return actions

    steps = env.run([wrapper, "pass"])
    metrics["reward"] = steps[-1][0].reward
    
    total_actions = sum(metrics["worker_actions"].values())
    productive_pct = metrics["worker_actions"]["PRODUCTIVE"] / max(1, total_actions)
    avg_water_backlog = sum(metrics["water_backlog"])/len(metrics["water_backlog"]) if metrics["water_backlog"] else 0
    
    avg_idle_tiles_per_day = metrics["idle_tiles_count"] / 720
    avg_plant_count = metrics["plant_count_sum"] / 720
    
    return {
        "seed": seed,
        "reward": metrics["reward"],
        "harvest_count": metrics["harvest_count"],
        "productive_pct": productive_pct,
        "avg_water_backlog": avg_water_backlog,
        "market_revenue": metrics["market_revenue"],
        "avg_idle_tiles": avg_idle_tiles_per_day,
        "avg_plant_count": avg_plant_count,
        "expansion_days": metrics["expansion_days"],
        "expansion_money": metrics["expansion_money_at_unlock"],
        "avg_cash_reserve": sum(metrics["cash_reserve_over_time"])/max(1, len(metrics["cash_reserve_over_time"]))
    }

def main():
    seeds = list(range(200, 240)) # Use 40 seeds for the parameter sweep search. We'll use 100 for final validation later.
    params = [60, 70, 80, 90, 100]
    
    print("Running Champion Baseline...")
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        champ_results = pool.map(run_simulation, [(s, True, 0) for s in seeds])
    champ_rewards = [r["reward"] for r in champ_results]
    champ_mean = statistics.mean(champ_rewards)
    
    print(f"\nChampion Mean Reward: ${champ_mean:.2f}")
    print(f"{'Threshold %':<12} | {'Mean Reward':<12} | {'Delta':<10} | {'Win Rate':<10} | {'Exp Days':<15} | {'Idle Tiles':<10} | {'Prod %'}")
    print("-" * 90)
    
    results_by_param = {}
    
    for thresh in params:
        args = [(s, False, thresh) for s in seeds]
        with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
            results = pool.map(run_simulation, args)
            
        rewards = [r["reward"] for r in results]
        mean_reward = statistics.mean(rewards)
        mean_revenue = statistics.mean([r["market_revenue"] for r in results])
        mean_harvests = statistics.mean([r["harvest_count"] for r in results])
        mean_prod = statistics.mean([r["productive_pct"] for r in results])
        mean_idle_tiles = statistics.mean([r["avg_idle_tiles"] for r in results])
        mean_water = statistics.mean([r["avg_water_backlog"] for r in results])
        mean_plant_count = statistics.mean([r["avg_plant_count"] for r in results])
        avg_cash_reserve = statistics.mean([r["avg_cash_reserve"] for r in results])
        
        # Calculate win rate vs champion
        wins = sum(1 for c, t in zip(champ_rewards, rewards) if t > c)
        win_rate = wins / len(seeds)
        delta = mean_reward - champ_mean
        
        # Avg expansion days across seeds
        exp_days_flat = [d for r in results for d in r["expansion_days"]]
        avg_exp_day = sum(exp_days_flat)/max(1, len(exp_days_flat)) if exp_days_flat else 0
        
        results_by_param[thresh] = {
            "reward": mean_reward,
            "delta_vs_champ": delta,
            "win_rate": win_rate,
            "market_revenue": mean_revenue,
            "harvests": mean_harvests,
            "productive_pct": mean_prod,
            "avg_idle_tiles": mean_idle_tiles,
            "water_backlog": mean_water,
            "avg_plant_count": mean_plant_count,
            "avg_exp_day": avg_exp_day,
            "avg_cash_reserve": avg_cash_reserve
        }
        
        print(f"{thresh:<12} | ${mean_reward:<11.2f} | ${delta:<9.2f} | {win_rate*100:<9.1f}% | Day {avg_exp_day:<11.1f} | {mean_idle_tiles:<10.1f} | {mean_prod*100:.1f}%")

    with open("phase2_sweep_results.json", "w") as f:
        json.dump(results_by_param, f, indent=2)
        
    print("\nPhase 2 Sweep complete. Execute `python phase2_sweep.py`")

if __name__ == "__main__":
    main()
