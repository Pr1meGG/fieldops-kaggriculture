import sys
import os
import multiprocessing
import pandas as pd
import numpy as np
from collections import defaultdict
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder

sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.state import ObservationParser, Position
from fieldops.constants import CROP_DATA
from fieldops.agent import MiniMelonAgent

class Exp006Tracker:
    def __init__(self):
        self.worker_travel = defaultdict(int)
        self.active_cycles = {} # pos -> cycle_id
        self.cycle_tasks = defaultdict(list)
        self.cycle_profits = defaultdict(float)
        self.next_cycle = 1
        
        self.empty_times = {}
        self.mature_times = {}
        self.unwatered_times = {}
        
        self.all_tasks = []

    def on_step_start(self, state):
        for y, row in enumerate(state.my_farm.tiles):
            for x, tile in enumerate(row):
                pos = (x, y)
                if tile.is_empty():
                    if pos not in self.empty_times:
                        self.empty_times[pos] = state.step
                    if pos in self.mature_times: del self.mature_times[pos]
                    if pos in self.unwatered_times: del self.unwatered_times[pos]
                elif tile.is_plant():
                    if pos in self.empty_times: del self.empty_times[pos]
                    
                    if not tile.watered_today:
                        if pos not in self.unwatered_times:
                            self.unwatered_times[pos] = state.step
                    else:
                        if pos in self.unwatered_times: del self.unwatered_times[pos]
                        
                    max_day = 4 if tile.crop == "MELON" else 4
                    is_mature = tile.planted_day is not None and (state.day - tile.planted_day) >= max_day
                    if is_mature:
                        if pos not in self.mature_times:
                            self.mature_times[pos] = state.step
                    else:
                        if pos in self.mature_times: del self.mature_times[pos]

    def on_agent_action(self, state, actions):
        my_farm = state.my_farm
        all_units = [my_farm.farmer] + list(my_farm.hands)
        unit_acts = [actions.get("farmer", ["PASS"])] + actions.get("hands", [])
        
        for i, (unit, act) in enumerate(zip(all_units, unit_acts)):
            unit_id = i
            pos = (unit.position.x, unit.position.y)
            tile = my_farm.tiles[pos[1]][pos[0]]
            
            if not act:
                continue
                
            cmd = act[0]
            if cmd in ["NORTH", "SOUTH", "EAST", "WEST"]:
                self.worker_travel[unit_id] += 1
            elif cmd == "PLANT":
                crop = act[1]
                cycle_id = self.next_cycle
                self.next_cycle += 1
                self.active_cycles[pos] = cycle_id
                
                delay = state.step - self.empty_times.get(pos, 0)
                profit = CROP_DATA[crop]["base_price"] * CROP_DATA[crop]["max_yield_unf"] - CROP_DATA[crop]["seed_cost"]
                
                task = {
                    "Task Type": "PLANT",
                    "Travel Distance": self.worker_travel[unit_id],
                    "Crop Age": 0,
                    "Remaining Days": 30 - state.day,
                    "Expected Harvest Value": profit,
                    "Task Delay": delay,
                    "Water Status": 0,
                    "Harvest Status": 0,
                    "cycle_id": cycle_id
                }
                self.cycle_tasks[cycle_id].append(task)
                self.all_tasks.append(task)
                self.worker_travel[unit_id] = 0
                
            elif cmd == "WATER":
                cycle_id = self.active_cycles.get(pos)
                if cycle_id:
                    crop = getattr(tile, 'crop', "MELON")
                    profit = CROP_DATA[crop]["base_price"] * CROP_DATA[crop]["max_yield_unf"] - CROP_DATA[crop]["seed_cost"]
                    delay = state.step - self.unwatered_times.get(pos, state.step - state.hour)
                    age = state.day - getattr(tile, 'planted_day', state.day) if getattr(tile, 'planted_day', None) is not None else 0
                    
                    task = {
                        "Task Type": "WATER",
                        "Travel Distance": self.worker_travel[unit_id],
                        "Crop Age": age,
                        "Remaining Days": 30 - state.day,
                        "Expected Harvest Value": profit,
                        "Task Delay": delay,
                        "Water Status": int(tile.watered_today),
                        "Harvest Status": 0,
                        "cycle_id": cycle_id
                    }
                    self.cycle_tasks[cycle_id].append(task)
                    self.all_tasks.append(task)
                self.worker_travel[unit_id] = 0
                
            elif cmd == "HARVEST":
                cycle_id = self.active_cycles.get(pos)
                if cycle_id:
                    crop = getattr(tile, 'crop', "MELON")
                    profit = CROP_DATA[crop]["base_price"] * CROP_DATA[crop]["max_yield_unf"] - CROP_DATA[crop]["seed_cost"]
                    delay = state.step - self.mature_times.get(pos, state.step)
                    age = state.day - getattr(tile, 'planted_day', state.day) if getattr(tile, 'planted_day', None) is not None else 0
                    
                    task = {
                        "Task Type": "HARVEST",
                        "Travel Distance": self.worker_travel[unit_id],
                        "Crop Age": age,
                        "Remaining Days": 30 - state.day,
                        "Expected Harvest Value": profit,
                        "Task Delay": delay,
                        "Water Status": int(tile.watered_today),
                        "Harvest Status": 1,
                        "cycle_id": cycle_id
                    }
                    self.cycle_tasks[cycle_id].append(task)
                    self.all_tasks.append(task)
                    
                    self.cycle_profits[cycle_id] = profit
                    del self.active_cycles[pos]
                self.worker_travel[unit_id] = 0
                
            elif cmd == "DROP":
                profit = 0
                for item, count in unit.inventory.items.items():
                    if item != "FERTILIZER" and count > 0:
                        profit += CROP_DATA.get(item, CROP_DATA["MELON"])["base_price"] * count
                task = {
                    "Task Type": "DROP",
                    "Travel Distance": self.worker_travel[unit_id],
                    "Crop Age": 0,
                    "Remaining Days": 30 - state.day,
                    "Expected Harvest Value": profit,
                    "Task Delay": 0,
                    "Water Status": 0,
                    "Harvest Status": 0,
                    "cycle_id": None,
                    "final_contribution": profit
                }
                self.all_tasks.append(task)
                self.worker_travel[unit_id] = 0

    def finalize(self):
        for task in self.all_tasks:
            if "final_contribution" not in task:
                cid = task.get("cycle_id")
                task["final_contribution"] = self.cycle_profits.get(cid, 0.0)
        return self.all_tasks

def run_simulation(seed):
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    agent = MiniMelonAgent()
    tracker = Exp006Tracker()
    
    def wrapper(obs, cfg=None):
        if hasattr(obs, 'step') and obs.step > 718:
            return agent(obs)
            
        try:
            state = ObservationParser.parse(obs)
            tracker.on_step_start(state)
            actions = agent(obs)
            tracker.on_agent_action(state, actions)
            return actions
        except Exception as e:
            return agent(obs)

    env.run([wrapper, "pass"])
    return tracker.finalize()

def main():
    seeds = list(range(800, 820)) # 20 seeds is plenty of data for ML (~100k tasks)
    print("EXP-006: Task Utility Discovery")
    print("Simulating environments and gathering executed tasks...")
    
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        results = pool.map(run_simulation, seeds)
        
    all_tasks = []
    for r in results:
        all_tasks.extend(r)
        
    df = pd.DataFrame(all_tasks)
    print(f"\nCollected {len(df):,} executed tasks.")
    
    # Preprocessing
    df = df.drop(columns=["cycle_id"])
    
    # Convert Task Type to dummy variables to prevent ordinal bias
    df = pd.get_dummies(df, columns=["Task Type"])
    
    X = df.drop(columns=["final_contribution"])
    y = df["final_contribution"]
    
    print("\nTraining Random Forest Regressor to discover utility function...")
    rf = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42, n_jobs=-1)
    rf.fit(X, y)
    
    importances = rf.feature_importances_
    features = X.columns
    
    ranked = sorted(zip(features, importances), key=lambda x: x[1], reverse=True)
    
    print("\n=========================================================")
    print("Task Feature Importance (Predictive of Final Day-30 Money)")
    print("=========================================================")
    for feat, imp in ranked:
        print(f"{feat:<25} | {imp*100:5.2f}%")
        
    print("\n=========================================================")
    print("Conclusion")
    print("=========================================================")
    print("These are the most critical signals for any future Priority/Utility Scheduler.")
    
if __name__ == "__main__":
    main()
