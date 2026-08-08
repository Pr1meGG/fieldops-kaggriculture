import sys
import os
import multiprocessing
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser
from fieldops.agent import MiniMelonAgent

def create_capped_agent(max_hands):
    class CappedAgent(MiniMelonAgent):
        def __call__(self, obs: dict) -> dict:
            if not isinstance(obs, dict): return super().__call__(obs)
            
            # Run base champion logic
            actions = super().__call__(obs)
            
            # Enforce strict worker cap
            state = ObservationParser.parse(obs)
            current_hands = len(state.my_farm.hands)
            
            if current_hands >= max_hands:
                # Strip HIRE actions
                actions["market"] = [a for a in actions["market"] if a[0] != "HIRE"]
            
            return actions
    return CappedAgent()

def run_worker_sweep(args):
    seed, max_hands = args
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    agent_inst = create_capped_agent(max_hands)
    
    def wrapper(obs, config=None):
        if getattr(obs, 'step', 0) > 718: return agent_inst(obs)
        try:
            return agent_inst(obs)
        except Exception:
            return {"farmer": ["PASS"]}
            
    env.run([wrapper, "pass"])
    reward = env.steps[-1][0].reward or 0
    
    return {
        "seed": seed,
        "max_hands": max_hands,
        "final_money": reward
    }

def main():
    seeds = list(range(1200, 1250)) # 50 seeds for speed
    caps = [2, 4, 6, 8, 10, 12, 14, 16]
    
    print("EXP-011: Worker Scaling Benchmark (Marginal Revenue Product)")
    print(f"Testing worker caps: {caps} over {len(seeds)} seeds...")
    
    tasks = [(s, c) for s in seeds for c in caps]
    
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        results = pool.map(run_worker_sweep, tasks)
        
    df = pd.DataFrame(results)
    
    print("\n=========================================================")
    print("Worker Scaling Marginal Revenue Product (MRP)")
    print("=========================================================")
    
    summary = df.groupby("max_hands")["final_money"].mean().reset_index()
    summary = summary.sort_values("max_hands")
    
    prev_money = None
    prev_hands = None
    
    for _, row in summary.iterrows():
        hands = int(row["max_hands"])
        money = row["final_money"]
        
        mrp = 0
        if prev_money is not None:
            mrp_per_worker = (money - prev_money) / (hands - prev_hands)
            print(f"Cap: {hands:2d} hands | Mean Reward: ${money:,.2f} | Marginal ROI/Worker: ${mrp_per_worker:+,.2f}")
        else:
            print(f"Cap: {hands:2d} hands | Mean Reward: ${money:,.2f} | Marginal ROI/Worker: N/A")
            
        prev_money = money
        prev_hands = hands

if __name__ == "__main__":
    main()
