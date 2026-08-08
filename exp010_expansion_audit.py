import sys
import os
import multiprocessing
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser
from fieldops.constants import CROP_DATA
from fieldops.agent import MiniMelonAgent

def get_quad_coords(quad_id):
    if quad_id == 1: return [(x, y) for y in range(0, 5) for x in range(5, 10)] # NE
    elif quad_id == 2: return [(x, y) for y in range(5, 10) for x in range(0, 5)] # SW
    elif quad_id == 3: return [(x, y) for y in range(5, 10) for x in range(5, 10)] # SE
    return []

class Exp010Tracker:
    def __init__(self, seed):
        self.seed = seed
        self.quad_purchases = [] # list of dicts
        self.active_quads = {} # quad_id -> { "purchased_step": int, "coords": list, "first_plant": None, "first_harvest": None, "profit": 0 }
        self.previous_quads = set(["NW"])
        
        self.empty_times = {} # pos -> step empty
        self.mature_times = {} # pos -> step mature
        
    def on_step_start(self, state, prev_state):
        if not prev_state: return
        my_farm = state.my_farm
        prev_farm = prev_state.my_farm
        
        current_quads = set(my_farm.unlocked_quadrants)
        new_quads = current_quads - self.previous_quads
        
        # Quadrant purchased!
        for q in new_quads:
            quad_id = len(self.previous_quads)
            self.previous_quads.add(q)
            
            workers = 1 + len(my_farm.hands)
            active_plants = sum(1 for row in my_farm.tiles for t in row if t.is_plant())
            total_unlocked = len(current_quads) * 25
            
            purchase_record = {
                "seed": self.seed,
                "quad_id": quad_id,
                "day_purchased": state.day,
                "money_before": prev_farm.money,
                "money_after": my_farm.money,
                "worker_count": workers,
                "active_planted_tiles": active_plants,
                "utilization": active_plants / (total_unlocked - 25), # util BEFORE this quadrant was added
                "idle_tile_percentage": 1.0 - (active_plants / (total_unlocked - 25))
            }
            self.quad_purchases.append(purchase_record)
            
            self.active_quads[quad_id] = {
                "purchased_step": state.step,
                "coords": set(get_quad_coords(quad_id)),
                "first_plant": None,
                "first_harvest": None,
                "profit": 0
            }
            
        # Check transitions for plants and harvests in active new quads
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                pos = (x, y)
                prev_tile = prev_farm.tiles[y][x]
                
                # Check if it was planted
                if prev_tile.is_empty() and tile.is_plant():
                    for qid, qdata in self.active_quads.items():
                        if pos in qdata["coords"]:
                            if qdata["first_plant"] is None:
                                qdata["first_plant"] = state.step
                                
                # Check if it was harvested
                if prev_tile.is_plant() and tile.is_empty():
                    crop = prev_tile.crop if hasattr(prev_tile, 'crop') else "MELON"
                    profit = CROP_DATA[crop]["base_price"] * CROP_DATA[crop]["max_yield_unf"] - CROP_DATA[crop]["seed_cost"]
                    for qid, qdata in self.active_quads.items():
                        if pos in qdata["coords"]:
                            qdata["profit"] += profit
                            if qdata["first_harvest"] is None:
                                qdata["first_harvest"] = state.step

    def finalize(self):
        for rec in self.quad_purchases:
            qid = rec["quad_id"]
            qdata = self.active_quads[qid]
            
            fp = qdata["first_plant"]
            fh = qdata["first_harvest"]
            
            rec["time_until_first_plant"] = (fp - qdata["purchased_step"]) if fp else None
            rec["time_until_first_harvest"] = (fh - qdata["purchased_step"]) if fh else None
            rec["total_profit_generated"] = qdata["profit"]
            
            cost = 1000 if qid == 1 else (2000 if qid == 2 else 4000)
            rec["roi"] = (qdata["profit"] - cost) / cost
            rec["payback_achieved"] = qdata["profit"] >= cost
            
        return self.quad_purchases

def run_audit(seed):
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    agent = MiniMelonAgent()
    tracker = Exp010Tracker(seed)
    
    prev_state = None
    def wrapper(obs, config=None):
        nonlocal prev_state
        if getattr(obs, 'step', 0) > 718:
            return agent(obs)
            
        try:
            state = ObservationParser.parse(obs)
            tracker.on_step_start(state, prev_state)
            actions = agent(obs)
            prev_state = state
            return actions
        except Exception:
            return agent(obs)

    env.run([wrapper, "pass"])
    return tracker.finalize()

def main():
    seeds = list(range(1100, 1200))
    print("EXP-010: Dynamic Expansion Audit")
    print(f"Running {len(seeds)} seeds...")
    
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        results = pool.map(run_audit, seeds)
        
    all_purchases = []
    for r in results:
        all_purchases.extend(r)
        
    df = pd.DataFrame(all_purchases)
    print(f"\nCollected {len(df):,} quadrant purchases.")
    
    if len(df) > 0:
        print("\n=========================================================")
        print("Quadrant Purchase ROI Analysis")
        print("=========================================================")
        for qid in [1, 2, 3]:
            q_df = df[df["quad_id"] == qid]
            if len(q_df) == 0: continue
            
            mean_roi = q_df["roi"].mean()
            payback_rate = q_df["payback_achieved"].mean()
            avg_plant_delay = q_df["time_until_first_plant"].mean() / 24.0 # in days
            avg_util_before = q_df["utilization"].mean()
            
            print(f"Quadrant Tier {qid}:")
            print(f"  Count:                    {len(q_df)}")
            print(f"  Mean ROI:                 {mean_roi:+.1%}")
            print(f"  Payback Success Rate:     {payback_rate:.1%}")
            print(f"  Farm Util Before Buy:     {avg_util_before:.1%}")
            print(f"  Days until first plant:   {avg_plant_delay:.1f} days")
            print("")
            
        print("Conclusion: Negative ROI purchases indicate capital should have been deployed to workers or seeds instead.")

if __name__ == "__main__":
    main()
