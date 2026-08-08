import logging
from typing import Any, List, Tuple
from fieldops.state import Position
from fieldops.core.planner import BaseManager
from fieldops.managers.worker_manager import WorkerManager, _distance, _choose_movement

logger = logging.getLogger(__name__)

class CandidateWorkerManager(WorkerManager):
    def __init__(self):
        self.animal_unfed_days = {} # dict of id(tile) to days unfed? Or pos to days unfed?
        self.last_day = -1
        
    def execute(self, state, context):
        my_farm = state.my_farm
        all_units = [my_farm.farmer] + list(my_farm.hands)
        available_units = list(all_units)
        
        unit_actions_map = {id(u): ["PASS"] for u in all_units}
        
        # Track days unfed
        if state.day != self.last_day:
            self.last_day = state.day
            for y, row in enumerate(my_farm.tiles):
                for x, tile in enumerate(row):
                    if tile.has_animal():
                        pos = (x, y)
                        if not getattr(tile, 'fed_today', False):
                            self.animal_unfed_days[pos] = self.animal_unfed_days.get(pos, 0) + 1
                        else:
                            self.animal_unfed_days[pos] = 0
        
        tasks = [] # (pos, t_type, priority, data)
        
        # 1. Harvest & Collect (900)
        # 2. Water (800)
        # 3. Plant (400)
        # 4. Feed (700 normal, 950 emergency)
        # 5. Care (600)
        # 6. Drop (1000)
        
        shed_pos = Position(4, 4)
        
        # Drop logic
        for u in all_units:
            if any(c > 0 for i, c in u.inventory.items.items() if i != "FERTILIZER" and i not in ["WHEAT", "COW", "SHEEP"]):
                tasks.append((shed_pos, "DROP", 1000, {"unit_id": id(u)}))
                
        # Tile-centric tasks
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                pos = Position(x, y)
                
                # Crops
                if getattr(tile, 'kind', '') == "PLANT":
                    planted_day = getattr(tile, 'planted_day', None)
                    if planted_day is not None:
                        # Harvest?
                        crop = getattr(tile, 'crop', '')
                        # proper maturity check using CROP_DATA
                        from fieldops.constants import CROP_DATA
                        crop = getattr(tile, 'crop', '')
                        max_day = CROP_DATA.get(crop, {}).get("max_yield_day", 999)
                        if (state.day - planted_day) >= max_day:
                            tasks.append((pos, "HARVEST", 900, {}))
                        elif not getattr(tile, 'watered_today', False):
                            tasks.append((pos, "WATER", 800, {}))
                            
                elif getattr(tile, 'is_empty', lambda: False)():
                    tasks.append((pos, "PLANT", 400, {}))
                    
                # Livestock
                if getattr(tile, 'has_animal', lambda: False)():
                    if tile.is_harvestable():
                        tasks.append((pos, "HARVEST", 900, {}))
                        
                    if not getattr(tile, 'fed_today', False):
                        days_unfed = self.animal_unfed_days.get((x,y), 0)
                        priority = 950 if days_unfed >= 2 else 700
                        tasks.append((pos, "FEED", priority, {}))
                        
                    if tile.animal == "SHEEP" and not getattr(tile, 'cared_today', False):
                        tasks.append((pos, "CARE", 600, {}))
                        
                # Fertilizer
                if getattr(tile, 'fertilizer_available', False):
                    tasks.append((pos, "COLLECT_FERTILIZER", 900, {}))
                    
                # Empty pastures
                if getattr(tile, 'kind', '') == "PASTURE" and not getattr(tile, 'has_animal', lambda: False)():
                    # We might need to place an animal
                    tasks.append((pos, "PLACE", 500, {}))
                    
        # Check if we need to build a pasture
        build_pasture = getattr(context, "build_pasture", None)
        if build_pasture:
            tasks.append((build_pasture, "BUILD_PASTURE", 950, {}))
                    
        # Sort tasks by priority
        tasks.sort(key=lambda t: t[2], reverse=True)
        
        # Track how many empty pastures we assigned
        handled_empty_pastures = set()
        
        # Assignment loop
        for task in tasks:
            if not available_units:
                break
                
            pos, t_type, priority, data = task
            
            if t_type == "DROP":
                # Only the specific unit can drop its own inventory
                uid = data["unit_id"]
                u = next((unit for unit in available_units if id(unit) == uid), None)
                if u:
                    if _distance(u.position, pos) <= 1:
                        unit_actions_map[id(u)] = ["DROP"]
                    else:
                        unit_actions_map[id(u)] = [_choose_movement(u.position, pos)]
                    available_units.remove(u)
                continue
                
            # Find best unit
            best_unit = min(available_units, key=lambda u: _distance(u.position, pos))
            
            if t_type == "FEED":
                if best_unit.inventory.items.get("WHEAT", 0) > 0:
                    if best_unit.position == pos:
                        unit_actions_map[id(best_unit)] = ["FEED"]
                    else:
                        unit_actions_map[id(best_unit)] = [_choose_movement(best_unit.position, pos)]
                    available_units.remove(best_unit)
                else:
                    # Needs wheat
                    if best_unit.position == shed_pos:
                        unit_actions_map[id(best_unit)] = ["PICKUP", "WHEAT"]
                    else:
                        unit_actions_map[id(best_unit)] = [_choose_movement(best_unit.position, shed_pos)]
                    available_units.remove(best_unit)
                    
            elif t_type == "PLACE":
                if pos in handled_empty_pastures: continue
                # Do we hold an animal?
                held_animal = next((i for i, c in best_unit.inventory.items.items() if i in ["COW", "SHEEP"] and c > 0), None)
                if held_animal:
                    if best_unit.position == pos:
                        unit_actions_map[id(best_unit)] = ["PLACE", held_animal]
                    else:
                        unit_actions_map[id(best_unit)] = [_choose_movement(best_unit.position, pos)]
                    available_units.remove(best_unit)
                    handled_empty_pastures.add(pos)
                else:
                    # Check if shed has animals
                    animals_in_shed = [a for a in ["COW", "SHEEP"] if my_farm.shed.items.get(a, 0) > 0]
                    if animals_in_shed:
                        if best_unit.position == shed_pos:
                            unit_actions_map[id(best_unit)] = ["PICKUP", animals_in_shed[0]]
                        else:
                            unit_actions_map[id(best_unit)] = [_choose_movement(best_unit.position, shed_pos)]
                        available_units.remove(best_unit)
                        handled_empty_pastures.add(pos)
                        
            elif t_type == "PLANT":
                crop_to_plant = getattr(context, "target_crop", "MELON")
                if my_farm.seeds and my_farm.seeds.get(crop_to_plant, 0) > 0:
                    if best_unit.position == pos:
                        unit_actions_map[id(best_unit)] = ["PLANT", crop_to_plant]
                    else:
                        unit_actions_map[id(best_unit)] = [_choose_movement(best_unit.position, pos)]
                    available_units.remove(best_unit)
                    # Deduct seed logically so we don't plan to plant if out of seeds
                    my_farm.seeds[crop_to_plant] -= 1
                    
            elif t_type in ["HARVEST", "COLLECT_FERTILIZER"]:
                is_animal = getattr(state.my_farm.tiles[pos.y][pos.x], 'has_animal', lambda: False)()
                if is_animal or t_type == "COLLECT_FERTILIZER":
                    # Collecting from an animal or fertilizer puts item in inventory.
                    # We must empty our inventory first if we hold incompatible things like WHEAT.
                    inv_items = sum(best_unit.inventory.items.values())
                    if inv_items > 0:
                        if best_unit.position == shed_pos:
                            unit_actions_map[id(best_unit)] = ["DROP"]
                        else:
                            unit_actions_map[id(best_unit)] = [_choose_movement(best_unit.position, shed_pos)]
                        available_units.remove(best_unit)
                        continue
                        
                if best_unit.position == pos:
                    unit_actions_map[id(best_unit)] = [t_type]
                else:
                    unit_actions_map[id(best_unit)] = [_choose_movement(best_unit.position, pos)]
                available_units.remove(best_unit)

            else:
                # WATER, CARE
                if best_unit.position == pos:
                    unit_actions_map[id(best_unit)] = [t_type]
                else:
                    unit_actions_map[id(best_unit)] = [_choose_movement(best_unit.position, pos)]
                available_units.remove(best_unit)

        # Context output: pending workload
        context.pending_workload = len(tasks)
        context.unwatered_count = sum(1 for t in tasks if t[1] == "WATER")
        context.livestock_tasks = sum(1 for t in tasks if t[1] in ["FEED", "CARE", "HARVEST" if getattr(state.my_farm.tiles[t[0].y][t[0].x], 'has_animal', lambda: False)() else ""])
        
        return {
            "farmer": unit_actions_map[id(my_farm.farmer)],
            "hands": [unit_actions_map[id(u)] for u in my_farm.hands]
        }

class CandidateEconomyManager(BaseManager):
    def initialize(self, context): pass
    def update(self, state, context): pass
    def plan(self, state, context): pass
    
    def __init__(self):
        self.hires_ordered = 0
        self.cows_ordered = 0
        self.sheep_ordered = 0
        self.workload_history = []
        
    def execute(self, state, context):
        actions = {"market": []}
        my_farm = state.my_farm
        money = my_farm.money
        
        # Opening liquidation (Day 0)
        if state.step == 0:
            if my_farm.shed.items.get("CARROT", 0) > 0:
                actions["market"].append(["SELL", "CARROT", my_farm.shed.items["CARROT"]])
                
        # Worker Hiring
        pending_workload = getattr(context, "pending_workload", 0)
        self.workload_history.append(pending_workload)
        if len(self.workload_history) > 24:
            self.workload_history.pop(0)
            
        avg_workload = sum(self.workload_history) / len(self.workload_history)
        active_hands = len(my_farm.hands) + self.hires_ordered
        
        steps_remaining = 720 - state.step
        
        # Evaluate incremental revenue vs cost
        if steps_remaining > 50 and active_hands == 0 and len(self.workload_history) == 24:
            # Current capacity: 1 worker ~ 24 productive actions per day (minus movement)
            # If avg_workload is persistently high (>10 pending constantly), we are losing crops
            if avg_workload > 12:
                # Diminishing returns: 2nd worker is less efficient due to interference/movement
                expected_incremental_actions = 18 * (steps_remaining / 24)
                # Revenue per action is roughly 1.5 (Melon/Strawberry)
                expected_incremental_revenue = expected_incremental_actions * 1.5
                
                hire_cost = 5 * (steps_remaining / 24)
                movement_burden = 50 # Base inefficiency estimate
                opportunity_cost = 100 # Capital lockup
                
                if expected_incremental_revenue > hire_cost + movement_burden + opportunity_cost:
                    if money > 150: # Ensure we don't go bankrupt immediately
                        actions["market"].append(["HIRE"])
                        self.hires_ordered += 1
                        self.workload_history.clear()
            
        return actions

class CandidateMarketManager(BaseManager):
    def initialize(self, context): pass
    def update(self, state, context): pass
    def plan(self, state, context): pass
    
    def execute(self, state, context):
        actions = {"market": []}
        my_farm = state.my_farm
        money = my_farm.money
        
        steps_remaining = 720 - state.step
        liquidation_urgency = steps_remaining < 50
        
        # Sell logic
        for item, count in my_farm.shed.items.items():
            if count == 0 or item == "WHEAT":
                continue # Keep wheat for feed, handled separately
                
            current_price = state.market.prices.get(item, 0)
            
            # Simple thresholding based on replay opening-book evidence
            should_sell = liquidation_urgency
            if item == "MELON" and current_price >= 18: should_sell = True
            elif item == "STRAWBERRY" and current_price >= 8: should_sell = True
            elif item == "CARROT" and current_price >= 5: should_sell = True
            elif item in ["MILK", "WOOL"]: should_sell = True # Sell livestock products readily
            
            if should_sell:
                # Don't dump huge quantities at once unless urgent, to preserve price
                sell_amount = count if liquidation_urgency else min(count, 10)
                actions["market"].append(["SELL", item, sell_amount])
                
        # Manage Wheat reserves
        total_animals = sum(1 for row in my_farm.tiles for t in row if getattr(t, 'has_animal', lambda: False)())
        total_animals += my_farm.shed.items.get("COW", 0) + my_farm.shed.items.get("SHEEP", 0)
        
        wheat_held = my_farm.shed.items.get("WHEAT", 0)
        if total_animals > 0 and wheat_held < total_animals * 10:
            need_wheat = (total_animals * 10) - wheat_held
            cost = need_wheat * state.market.prices.get("WHEAT", 5) # approx
            if money > cost + 50:
                actions["market"].append(["BUY_PRODUCT", "WHEAT", need_wheat])
                
        # Sell excess wheat
        if wheat_held > total_animals * 20 and not liquidation_urgency:
            actions["market"].append(["SELL", "WHEAT", wheat_held - (total_animals * 15)])
            
        if liquidation_urgency and wheat_held > 0:
            actions["market"].append(["SELL", "WHEAT", wheat_held])
            
        return actions

class CandidateCropManager(BaseManager):
    def initialize(self, context): pass
    def update(self, state, context): pass
    def plan(self, state, context): pass
    
    def execute(self, state, context):
        actions = {"market": []}
        my_farm = state.my_farm
        money = my_farm.money
        steps_remaining = 720 - state.step
        
        current_plants = sum(1 for row in my_farm.tiles for t in row if getattr(t, 'kind', '') == "PLANT")
        max_plants = 12 # Capacity
        
        # Determine best crop dynamically
        # Crop cycle times: Melon (250), Strawberry (120), Carrot (50), Wheat (100)
        # Expected yields: Melon (12), Strawberry (6), Carrot (3), Wheat (5)
        # Expected prices: Melon (20), Strawberry (10), Carrot (5), Wheat (6)
        # Cost: Melon (10), Strawberry (8), Carrot (3), Wheat (5)
        
        candidates = [
            ("MELON", 250, 12, 18, 10),
            ("STRAWBERRY", 120, 6, 9, 8),
            ("WHEAT", 100, 5, 5, 5),
            ("CARROT", 50, 3, 5, 3)
        ]
        
        best_crop = None
        best_roi = -9999
        
        for crop, cycle, yield_amt, exp_price, cost in candidates:
            if cycle + 20 > steps_remaining: # 20 step buffer for harvest/sell
                continue
            
            # Simple expected revenue
            revenue = yield_amt * exp_price
            profit = revenue - cost
            roi = profit / cycle
            
            # Boost Wheat slightly if we need feed
            total_animals = sum(1 for row in my_farm.tiles for t in row if getattr(t, 'has_animal', lambda: False)())
            if crop == "WHEAT" and my_farm.shed.items.get("WHEAT", 0) < total_animals * 15:
                roi += 0.5 # Priority boost for feed
                
            if roi > best_roi:
                best_roi = roi
                best_crop = crop
                
        if best_crop is None:
            # Nothing can mature in time
            return actions
            
        context.target_crop = best_crop
        
        seeds_held = my_farm.seeds.get(best_crop, 0) if my_farm.seeds else 0
        need_seeds = max_plants - current_plants - seeds_held
        
        if need_seeds > 0:
            seed_price = next(c[4] for c in candidates if c[0] == best_crop)
            if money >= need_seeds * seed_price + 20: # keep 20 buffer
                actions["market"].append(["BUY_SEED", best_crop, need_seeds])
                
        return actions

class CandidateLivestockManager(BaseManager):
    def initialize(self, context): pass
    def update(self, state, context): pass
    def plan(self, state, context): pass
    
    def __init__(self):
        self.cows_bought = 0
        self.sheep_bought = 0
        
    def execute(self, state, context):
        actions = {"market": []}
        my_farm = state.my_farm
        money = my_farm.money
        
        owned_cows = my_farm.shed.items.get("COW", 0) + sum(1 for row in my_farm.tiles for t in row if getattr(t, 'animal', None) == "COW") + self.cows_bought
        owned_sheep = my_farm.shed.items.get("SHEEP", 0) + sum(1 for row in my_farm.tiles for t in row if getattr(t, 'animal', None) == "SHEEP") + self.sheep_bought
        pastures = sum(1 for row in my_farm.tiles for t in row if t.kind == "PASTURE")
        
        target_cows = 1
        target_sheep = 1
        
        # Re-invest heavily early on
        if state.day > 10 and money > 1500:
            target_cows = 2
            target_sheep = 2
            
        if owned_cows < target_cows and pastures > (owned_cows + owned_sheep):
            if money >= 400 + 50:
                actions["market"].append(["BUY_ANIMAL", "COW", 1])
                self.cows_bought += 1
                money -= 400
        elif owned_sheep < target_sheep and pastures > (owned_cows + owned_sheep):
            if money >= 500 + 50:
                actions["market"].append(["BUY_ANIMAL", "SHEEP", 1])
                self.sheep_bought += 1
                money -= 500
                
        # Build pastures if needed
        pastures_built = sum(1 for row in my_farm.tiles for t in row if t.kind == "PASTURE")
        target_animals = target_cows + target_sheep
        if pastures_built < target_animals:
            # Check if there is an empty tile
            empty_tiles = [Position(x, y) for y, row in enumerate(my_farm.tiles) for x, tile in enumerate(row) if tile.is_empty()]
            if empty_tiles:
                best_pasture = min(empty_tiles, key=lambda p: abs(p.x - 4) + abs(p.y - 4))
                # Add a high-priority BUILD_PASTURE task to context for the WorkerManager to pick up
                context.build_pasture = best_pasture
                
        return actions
