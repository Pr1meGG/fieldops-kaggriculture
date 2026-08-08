import sys, os, random, statistics
sys.path.insert(0, os.path.abspath("src"))

from kaggle_environments import make
from fieldops.state import ObservationParser
from fieldops.agent import agent as champion_agent
from fieldops.experimental.integrated_candidate_agent import integrated_candidate_agent

SEEDS = [1000, 1001, 1002]

def run_episode(config_name: str, seed: int):
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    trainer = env.train([None, "scratch/agent_pass.py"])
    obs = trainer.reset()
    

    
    metrics = {
        "final_cash": 0, "productive_actions": 0, "movement_actions": 0, "passes": 0,
        "worker_hires": 0, "animal_cost": 0, "feed_purchased": 0, "feed_cost": 0,
        "seed_cost": 0, "SELL": 0, "melons_sold": 0, "milk_sold": 0, "wool_sold": 0,
        "fert_sold": 0, "reward": 0
    }
    
    while True:
        if config_name == "CHAMPION":
            actions = champion_agent(obs)
        else:
            actions = integrated_candidate_agent(obs)
            
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
                metrics["SELL"] += 1
                metrics[f"SELL_{act[1]}"] = metrics.get(f"SELL_{act[1]}", 0) + act[2]
                if act[1] == "MELON": metrics["melons_sold"] += act[2]
                elif act[1] == "MILK": metrics["milk_sold"] += act[2]
                elif act[1] == "WOOL": metrics["wool_sold"] += act[2]
                elif act[1] == "FERTILIZER": metrics["fert_sold"] += act[2]
                
        # Track actions
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
                else:
                    metrics[a] = 1
                    
                if a == "PLANT":
                    crop = act[1] if len(act) > 1 else "UNKNOWN"
                    metrics[f"PLANT_{crop}"] = metrics.get(f"PLANT_{crop}", 0) + 1
                
        obs, reward, done, info = trainer.step(actions)
        if done: break
        
    metrics["reward"] = reward
    # Return last reward which equals cash + inventory
    metrics["final_cash"] = reward
    return metrics

def run_config(config_name):
    seeds = [1, 2, 3]
    results = []
    print(f"Running {config_name} over {len(seeds)} seeds sequentially...")
    for s in seeds:
        res = run_episode(config_name, s)
        results.append(res)
    
    # Average
    avg = {}
    for k in results[0]:
        avg[k] = sum(r.get(k, 0) for r in results) / len(results)
    return avg

def main():
    print("Starting INTEGRATED CANDIDATE Validation...")
    
    res_A = run_config("CHAMPION")
    res_C = run_config("CANDIDATE")
    
    # Print the report
    report = "### INTEGRATION VALIDATION\n\n"
    report += f"5 PM Champion:\nreward = ${res_A['final_cash']:.0f}\n\n"
    report += f"Integrated Candidate:\nreward = ${res_C['final_cash']:.0f}\n"
    report += f"Shed Items Sold (Config C):\n"
    for k, v in res_C.items():
        if k.startswith("SELL_") or k.startswith("PLANT_"):
            report += f"{k} = {v:.1f}\n"
    report += "\n"
    
    report += "### DELTAS\n"
    report += f"Candidate - Champion = ${res_C['final_cash'] - res_A['final_cash']:.0f}\n"
    report += f"Candidate - Local-First ($35,699) = ${res_C['final_cash'] - 35699:.0f}\n\n"
    
    # additional revenue (Milk + Wool + Fert * their prices)
    additional_revenue = res_C['milk_sold']*150 + res_C['wool_sold']*200 + res_C['fert_sold']*50
    report += f"additional revenue = ${additional_revenue:.0f}\n"
    report += f"net incremental value (C - A) = ${res_C['final_cash'] - res_A['final_cash']:.0f}\n\n"
    
    report += "### PRODUCTION\n"
    report += f"Melons:\nA = {res_A['melons_sold']:.1f}\nC = {res_C['melons_sold']:.1f}\n\n"
    report += f"Milk:\nA = {res_A['milk_sold']:.1f}\nC = {res_C['milk_sold']:.1f}\n\n"
    report += f"Wool:\nA = {res_A['wool_sold']:.1f}\nC = {res_C['wool_sold']:.1f}\n\n"
    report += f"Fertilizer:\nA = {res_A['fert_sold']:.1f}\nC = {res_C['fert_sold']:.1f}\n\n"
    
    report += "### PRODUCTIVE ACTIONS DETAILS (Config C)\n"
    for a in ["PLANT", "WATER", "HARVEST", "FEED", "CARE", "COLLECT_FERTILIZER", "PICKUP", "PLACE", "DROP", "SELL"]:
        report += f"{a} = {res_C.get(a, 0):.1f}\n"
    report += "\n### LOGISTICS\n"
    report += f"Movement:\nA = {res_A['movement_actions']:.1f}\nC = {res_C['movement_actions']:.1f}\n\n"
    report += f"Productive:\nA = {res_A['productive_actions']:.1f}\nC = {res_C['productive_actions']:.1f}\n\n"
    
    print(report)
    with open("integration_report.md", "w") as f:
        f.write(report)

if __name__ == "__main__":
    main()
