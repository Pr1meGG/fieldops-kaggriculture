import sys, os
sys.path.insert(0, os.path.abspath("src"))

from kaggle_environments import make
from fieldops.state import ObservationParser
from fieldops.agent import agent as champion_agent

def run_champion(seed: int):
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    trainer = env.train([None, "scratch/agent_pass.py"])
    obs = trainer.reset()
    
    metrics = {
        "final_cash": 0, "productive_actions": 0, "movement_actions": 0,
        "worker_hires": 0, "SELL": 0, "melons_sold": 0, "milk_sold": 0, "wool_sold": 0,
        "reward": 0, "melon_production": 0,
        "terminal_cash": 0
    }
    
    cash_trajectory = []
    
    while True:
        actions = champion_agent(obs)
        
        # Track market actions
        for act in actions.get("market", []):
            if not act: continue
            if act[0] == "HIRE":
                metrics["worker_hires"] += 1
            elif act[0] == "SELL":
                metrics["SELL"] += 1
                if act[1] == "MELON": metrics["melons_sold"] += act[2]
                
        # Track worker actions
        units = [actions.get("farmer", ["PASS"])] + actions.get("hands", [])
        for act in units:
            if not act: act = ["PASS"]
            a = act[0]
            if a in ["NORTH", "SOUTH", "EAST", "WEST"]: metrics["movement_actions"] += 1
            elif a != "PASS": 
                metrics["productive_actions"] += 1
                if a == "HARVEST":
                    # We assume it's melon production since champion doesn't do livestock
                    metrics["melon_production"] += 1
                
        obs, reward, done, info = trainer.step(actions)
        
        if done: 
            metrics["terminal_cash"] = state.my_farm.money if 'state' in locals() else 0
            break
            
        if obs.get('step', 0) >= 719:
            continue
            
        state = ObservationParser.parse(obs)
        cash_trajectory.append(state.my_farm.money)
        
    metrics["reward"] = reward
    metrics["final_cash"] = reward
    metrics["inventory"] = sum(state.my_farm.shed.items.values()) if state.my_farm.shed else 0
    metrics["land_count"] = 100 # Board is 100 tiles, unlock is not really tracked here but we can assume it's 10x10 unlocked?
    
    # Calculate actual workers (farmer + hands)
    metrics["worker_count"] = 1 + len(state.my_farm.hands)
    
    return metrics, cash_trajectory

def main():
    seeds = [1, 2, 3]
    results = []
    
    print("REPRODUCING 5 PM CHAMPION ON SEEDS 1, 2, 3")
    
    for s in seeds:
        print(f"Running seed {s}...")
        res, cash = run_champion(s)
        results.append(res)
        print(f"Seed {s} Reward: ${res['reward']:.0f}")
        
    avg = {}
    for k in results[0]:
        avg[k] = sum(r.get(k, 0) for r in results) / len(results)
        
    print("\nAVERAGE RESULTS:")
    print(f"Final Reward: ${avg['reward']:.0f}")
    print(f"Terminal Cash: ${avg['terminal_cash']:.0f}")
    print(f"Productive Actions: {avg['productive_actions']:.1f}")
    print(f"Movement Actions: {avg['movement_actions']:.1f}")
    print(f"Melon Production (Harvests): {avg['melon_production']:.1f}")
    print(f"Melons Sold: {avg['melons_sold']:.1f}")
    print(f"Worker Count: {avg['worker_count']:.1f}")
    print(f"Worker Hires: {avg['worker_hires']:.1f}")
    print(f"Inventory at End: {avg['inventory']:.1f}")

if __name__ == "__main__":
    main()
