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
                return actions
                
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
        "market_revenue": 0,
        "idle_tiles_count": 0,
        "plant_count_sum": 0,
        "cash_reserve_over_time": []
    }
    
    # Quadrant tracking
    quads = {
        2: {"cost": 1000, "unlocked": False},
        3: {"cost": 2000, "unlocked": False},
        4: {"cost": 4000, "unlocked": False}
    }
    
    def get_quad_idx(x, y):
        if x < 5 and y < 5: return 1
        if x >= 5 and y < 5: return 2
        if x < 5 and y >= 5: return 3
        if x >= 5 and y >= 5: return 4
        return 1

    def wrapper(obs, cfg=None):
        if not isinstance(obs, dict): return agent_instance(obs)
        step = obs.get("step", 0)
        state = ObservationParser.parse(obs)
        my_farm = state.my_farm
        
        # Track previous quads to detect unlocks
        prev_quad_count = len(my_farm.unlocked_quadrants)
        money_before = my_farm.money
        workers_count = 1 + len(my_farm.hands)
        
        water_backlog = 0
        idle_tiles_this_turn = 0
        plant_this_turn = 0
        
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                q = get_quad_idx(x, y)
                if q in quads and quads[q]["unlocked"]:
                    if tile.is_plant():
                        if "first_plant_step" not in quads[q]:
                            quads[q]["first_plant_step"] = step
                if tile.is_plant():
                    plant_this_turn += 1
                    if not tile.watered_today: water_backlog += 1
                if tile.is_empty():
                    idle_tiles_this_turn += 1
                    
        metrics["water_backlog"].append(water_backlog)
        metrics["idle_tiles_count"] += idle_tiles_this_turn
        metrics["plant_count_sum"] += plant_this_turn
        if step % 24 == 0: metrics["cash_reserve_over_time"].append(my_farm.money)
        
        actions = agent_instance(obs)
        
        # We need to peek into actions to see if BUY_LAND happened
        buying_land = any(a[0] == "BUY_LAND" for a in actions.get("market", []))
        if buying_land:
            target_q = prev_quad_count + 1
            if target_q in quads and not quads[target_q]["unlocked"]:
                total_tiles = prev_quad_count * 25
                util_pct = (plant_this_turn / total_tiles) * 100 if total_tiles > 0 else 100
                quads[target_q]["unlocked"] = True
                quads[target_q]["unlock_day"] = state.day
                quads[target_q]["unlock_hour"] = state.hour
                quads[target_q]["money_before"] = money_before
                quads[target_q]["workers_at_unlock"] = workers_count
                quads[target_q]["utilization_at_unlock"] = util_pct
                quads[target_q]["harvests"] = 0
                quads[target_q]["revenue"] = 0
                quads[target_q]["seed_cost"] = 0
                quads[target_q]["worker_actions"] = 0

        # Track quadrant events (harvest, plant, work)
        all_units = [my_farm.farmer] + list(my_farm.hands)
        unit_acts = [actions.get("farmer", ["PASS"])] + actions.get("hands", [])
        
        for unit, act in zip(all_units, unit_acts):
            if not act: continue
            a = act[0]
            
            # Simple attribution for actions: assign to the quadrant the unit is currently in
            q = get_quad_idx(unit.position.x, unit.position.y)
            if q in quads and quads[q]["unlocked"]:
                if a not in ["PASS"]:
                    quads[q]["worker_actions"] += 1
            
            if a in ["NORTH", "SOUTH", "EAST", "WEST"]: 
                metrics["worker_actions"]["MOVE"] += 1
            elif a == "PASS": 
                metrics["worker_actions"]["IDLE"] += 1
            else: 
                metrics["worker_actions"]["PRODUCTIVE"] += 1
                
            if a == "HARVEST":
                metrics["harvest_count"] += 1
                if q in quads and quads[q]["unlocked"]:
                    quads[q]["harvests"] += 1
                    if "first_harvest_step" not in quads[q]:
                        quads[q]["first_harvest_step"] = step
            if a == "SEED":
                if q in quads and quads[q]["unlocked"]:
                    # Assume melon
                    quads[q]["seed_cost"] += CROP_DATA["MELON"]["seed_cost"]

        for ma in actions.get("market", []):
            if ma[0] == "SELL":
                item = ma[1]
                qty = ma[2]
                price = state.market.prices.get(item, 0)
                metrics["market_revenue"] += price * qty
                # Naive attribution of revenue to quadrants based on harvest ratio
                # We'll do this post-simulation.
            
        return actions

    steps = env.run([wrapper, "pass"])
    metrics["reward"] = steps[-1][0].reward
    
    total_actions = sum(metrics["worker_actions"].values())
    productive_pct = metrics["worker_actions"]["PRODUCTIVE"] / max(1, total_actions)
    avg_water_backlog = sum(metrics["water_backlog"])/len(metrics["water_backlog"]) if metrics["water_backlog"] else 0
    avg_idle_tiles_per_day = metrics["idle_tiles_count"] / 720
    avg_plant_count = metrics["plant_count_sum"] / 720
    
    # Distribute revenue to quadrants proportionally by harvests
    total_harvests = metrics["harvest_count"]
    for q, data in quads.items():
        if data["unlocked"] and total_harvests > 0:
            ratio = data["harvests"] / total_harvests
            data["revenue"] = metrics["market_revenue"] * ratio
            
            # Profit = Revenue - LandCost - SeedCost - (WorkerActions * ApproxActionCost)
            # Worker hiring costs are a sunk cost, but we can amortize. We will just use (Revenue - Seed - Land)
            data["profit"] = data["revenue"] - data["seed_cost"] - data["cost"]
            data["roi"] = (data["profit"] / data["cost"]) * 100 if data["cost"] > 0 else 0
            
            time_to_plant = (data.get("first_plant_step", 720) - (data["unlock_day"]*24 + data["unlock_hour"]))
            data["time_to_plant_hours"] = time_to_plant
            time_to_harvest = (data.get("first_harvest_step", 720) - (data["unlock_day"]*24 + data["unlock_hour"]))
            data["time_to_harvest_hours"] = time_to_harvest
            
    return {
        "seed": seed,
        "reward": metrics["reward"],
        "harvest_count": metrics["harvest_count"],
        "productive_pct": productive_pct,
        "avg_water_backlog": avg_water_backlog,
        "market_revenue": metrics["market_revenue"],
        "avg_idle_tiles": avg_idle_tiles_per_day,
        "avg_plant_count": avg_plant_count,
        "avg_cash_reserve": sum(metrics["cash_reserve_over_time"])/max(1, len(metrics["cash_reserve_over_time"])),
        "quads": quads
    }

def main():
    seeds = list(range(200, 240)) # 40 seeds for sweep
    params = [60, 70, 80, 90, 100]
    
    print("Running Champion Baseline...")
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        champ_results = pool.map(run_simulation, [(s, True, 0) for s in seeds])
    champ_rewards = [r["reward"] for r in champ_results]
    champ_mean = statistics.mean(champ_rewards)
    
    results_by_param = {}
    
    print(f"\nChampion Mean Reward: ${champ_mean:.2f}")
    
    for thresh in params:
        print(f"Running Sweep: {thresh}%...")
        args = [(s, False, thresh) for s in seeds]
        with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
            results = pool.map(run_simulation, args)
            
        rewards = [r["reward"] for r in results]
        mean_reward = statistics.mean(rewards)
        win_rate = sum(1 for c, t in zip(champ_rewards, rewards) if t > c) / len(seeds)
        
        # Aggregate Q2, Q3, Q4 stats across seeds
        quad_stats = {2: {}, 3: {}, 4: {}}
        for q in [2, 3, 4]:
            q_profits = [r["quads"][q].get("profit", 0) for r in results if r["quads"][q]["unlocked"]]
            q_days = [r["quads"][q].get("unlock_day", 0) for r in results if r["quads"][q]["unlocked"]]
            q_util = [r["quads"][q].get("utilization_at_unlock", 0) for r in results if r["quads"][q]["unlocked"]]
            
            quad_stats[q] = {
                "unlock_rate": len(q_profits) / len(seeds),
                "avg_profit": statistics.mean(q_profits) if q_profits else 0,
                "avg_unlock_day": statistics.mean(q_days) if q_days else 0,
                "avg_utilization": statistics.mean(q_util) if q_util else 0
            }
            
        results_by_param[thresh] = {
            "reward": mean_reward,
            "delta_vs_champ": mean_reward - champ_mean,
            "win_rate": win_rate,
            "harvests": statistics.mean([r["harvest_count"] for r in results]),
            "avg_idle_tiles": statistics.mean([r["avg_idle_tiles"] for r in results]),
            "water_backlog": statistics.mean([r["avg_water_backlog"] for r in results]),
            "quad_stats": quad_stats,
            "raw_results": results
        }
        print(f"  {thresh}% -> Mean: ${mean_reward:.2f} (Delta: ${mean_reward - champ_mean:.2f}), Win Rate: {win_rate*100:.1f}%")

    with open("phase2_advanced_sweep_results.json", "w") as f:
        json.dump(results_by_param, f, indent=2)
        
    print("\nPhase 2 Parameter Sweep complete. Best threshold is the one with highest Mean Reward.")

if __name__ == "__main__":
    main()
