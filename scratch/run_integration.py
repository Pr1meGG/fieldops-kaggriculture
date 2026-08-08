import sys, os, random, statistics
sys.path.insert(0, os.path.abspath("src"))

from kaggle_environments import make
from fieldops.state import ObservationParser
from fieldops.agent import agent as champion_agent
from fieldops.experimental.integrated_agent import integrated_agent

SEEDS = [1000, 1001, 1002]

def run_episode(config_name: str, workers: int, cows: int, sheep: int, seed: int):
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    trainer = env.train([None, "scratch/agent_pass.py"])
    obs = trainer.reset()
    
    agent_config = {
        "hire_worker": (workers == 2),
        "target_cows": cows,
        "target_sheep": sheep
    }
    
    # Metrics
    metrics = {
        "reward": 0, "final_cash": 0, "starting_cash": 1000, "workers": workers,
        "worker_hires": 0, "land": 1, "animals": cows + sheep, "animal_escapes": 0,
        "melons_sold": 0, "milk_sold": 0, "wool_sold": 0, "fert_sold": 0,
        "feed_purchased": 0, "feed_cost": 0, "seed_cost": 0, "animal_cost": 0,
        "productive_actions": 0, "movement_actions": 0, "passes": 0,
        "PLANT": 0, "WATER": 0, "HARVEST": 0, "FEED": 0, "CARE": 0, "COLLECT_FERTILIZER": 0,
        "PICKUP": 0, "PLACE": 0, "DROP": 0, "SELL": 0, "worker_utilization": 0.0,
        "movement_productive_ratio": 0.0, "final_weeds": 0
    }
    
    while not env.done:
        if config_name == "A":
            actions = champion_agent(obs)
        else:
            actions = integrated_agent(obs, agent_config)
            
        state = None
        if obs.get("step", 0) <= 718:
            state = ObservationParser.parse(obs)
        
        # Track market actions
        for act in actions.get("market", []):
            if not act: continue
            if act[0] == "HIRE":
                metrics["worker_hires"] += 1
            elif act[0] == "BUY_ANIMAL":
                count = act[2]
                metrics["animal_cost"] += count * (400 if act[1] == "COW" else 500)
            elif act[0] == "BUY_PRODUCT" and act[1] == "WHEAT":
                metrics["feed_purchased"] += act[2]
                metrics["feed_cost"] += act[2] * 5
            elif act[0] == "BUY_SEED":
                metrics["seed_cost"] += act[2] * 10
            elif act[0] == "SELL":
                metrics["SELL"] += act[2]
                if act[1] == "MELON": metrics["melons_sold"] += act[2]
                elif act[1] == "MILK": metrics["milk_sold"] += act[2]
                elif act[1] == "WOOL": metrics["wool_sold"] += act[2]
                elif act[1] == "FERTILIZER": metrics["fert_sold"] += act[2]
                
        # Track unit actions
        units = [actions.get("farmer", ["PASS"])] + actions.get("hands", [])
        for act in units:
            if not act: act = ["PASS"]
            a = act[0]
            if a == "PASS": metrics["passes"] += 1
            elif a in ["NORTH", "SOUTH", "EAST", "WEST"]: metrics["movement_actions"] += 1
            else: 
                metrics["productive_actions"] += 1
                if a in metrics:
                    metrics[a] += 1
                
        obs, reward, done, info = trainer.step(actions)
        
    metrics["reward"] = reward
    
    # We can't parse final state because of step limits, but the last valid state is what we want
    # However, final cash is best gotten from the observation dict directly!
    metrics["final_cash"] = obs.get("player1", {}).get("cash", 0) # wait, obs in Kaggle contains players?
    # Actually, obs is just the raw obs dict from the step. We can just use reward for final cash!
    metrics["final_cash"] = reward
    
    tot = metrics["productive_actions"] + metrics["movement_actions"] + metrics["passes"]
    metrics["worker_utilization"] = (metrics["productive_actions"] + metrics["movement_actions"]) / tot if tot > 0 else 0
    metrics["movement_productive_ratio"] = metrics["movement_actions"] / metrics["productive_actions"] if metrics["productive_actions"] > 0 else 0
    
    return metrics

def run_config(config_name: str, workers: int, cows: int, sheep: int):
    results = []
    print(f"\nRunning {config_name} over 3 seeds sequentially...")
    for s in SEEDS:
        res = run_episode(config_name, workers, cows, sheep, s)
        results.append(res)
    
    # Average the metrics
    avg = {}
    for k in results[0]:
        avg[k] = sum(r[k] for r in results) / len(results)
    return avg

def main():
    print("Starting INTEGRATION PHASE Validation...")
    
    # A: Current Champion (12 Melons, no livestock). Champion actually hires 1 hand on step 0!
    # Wait, the champion hires 1 hand, so it's 2 workers.
    # We will pass workers=2 for our records.
    res_A = run_config("A", workers=2, cows=0, sheep=0)
    
    # B: Integrated Agent, 1 worker, 1 Cow, 1 Sheep
    res_B = run_config("B", workers=1, cows=1, sheep=1)
    
    # C: Integrated Agent, 2 workers, 1 Cow, 1 Sheep
    res_C = run_config("C", workers=2, cows=1, sheep=1)
    
    # Print the report
    report = "### INTEGRATION VALIDATION\n\n"
    report += f"Control A:\nreward = ${res_A['final_cash']:.0f}\n\n"
    report += f"1W + livestock B:\nreward = ${res_B['final_cash']:.0f}\n\n"
    report += f"2W + livestock C:\nreward = ${res_C['final_cash']:.0f}\n\n"
    
    report += "### DELTAS\n"
    report += f"B - A = ${res_B['final_cash'] - res_A['final_cash']:.0f}\n"
    report += f"C - A = ${res_C['final_cash'] - res_A['final_cash']:.0f}\n"
    report += f"C - B = ${res_C['final_cash'] - res_B['final_cash']:.0f}\n\n"
    
    # Economics (for Config C specifically, or we can just print the costs for C)
    additional_worker_cost = (res_C['worker_hires'] * 5 * 30) # roughly, but the reward is final cash so it's already deducted
    report += "### ECONOMICS (Config C)\n"
    report += f"additional worker cost (estimated) = ${res_C['worker_hires'] * 150:.0f}\n"
    report += f"livestock cost = ${res_C['animal_cost']:.0f}\n"
    report += f"feed cost = ${res_C['feed_cost']:.0f}\n"
    # additional revenue (Milk + Wool + Fert * their prices)
    additional_revenue = res_C['milk_sold']*150 + res_C['wool_sold']*200 + res_C['fert_sold']*50
    report += f"additional revenue = ${additional_revenue:.0f}\n"
    report += f"net incremental value (C - A) = ${res_C['final_cash'] - res_A['final_cash']:.0f}\n\n"
    
    report += "### PRODUCTION\n"
    report += f"Melons:\nA = {res_A['melons_sold']:.1f}\nB = {res_B['melons_sold']:.1f}\nC = {res_C['melons_sold']:.1f}\n\n"
    report += f"Milk:\nA = {res_A['milk_sold']:.1f}\nB = {res_B['milk_sold']:.1f}\nC = {res_C['milk_sold']:.1f}\n\n"
    report += f"Wool:\nA = {res_A['wool_sold']:.1f}\nB = {res_B['wool_sold']:.1f}\nC = {res_C['wool_sold']:.1f}\n\n"
    report += f"Fertilizer:\nA = {res_A['fert_sold']:.1f}\nB = {res_B['fert_sold']:.1f}\nC = {res_C['fert_sold']:.1f}\n\n"
    
    report += "### PRODUCTIVE ACTIONS DETAILS (Config C)\n"
    for a in ["PLANT", "WATER", "HARVEST", "FEED", "CARE", "COLLECT_FERTILIZER", "PICKUP", "PLACE", "DROP", "SELL"]:
        report += f"{a} = {res_C[a]:.1f}\n"
    report += "\n### LOGISTICS\n"
    report += f"Movement:\nA = {res_A['movement_actions']:.1f}\nB = {res_B['movement_actions']:.1f}\nC = {res_C['movement_actions']:.1f}\n\n"
    report += f"Productive:\nA = {res_A['productive_actions']:.1f}\nB = {res_B['productive_actions']:.1f}\nC = {res_C['productive_actions']:.1f}\n\n"
    report += f"Movement/Productive:\nA = {res_A['movement_productive_ratio']:.2f}\nB = {res_B['movement_productive_ratio']:.2f}\nC = {res_C['movement_productive_ratio']:.2f}\n\n"
    
    print(report)
    with open("integration_report.md", "w") as f:
        f.write(report)

if __name__ == "__main__":
    main()
