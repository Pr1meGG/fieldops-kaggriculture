from fieldops.core.planner import BaseManager
from fieldops.state import Position
from fieldops.constants import CROP_DATA, SHED_ADJACENT_TILES

def _distance(p1: Position, p2: Position) -> int:
    return abs(p1.x - p2.x) + abs(p1.y - p2.y)

def _choose_movement(current: Position, target: Position) -> str:
    dx = target.x - current.x
    dy = target.y - current.y
    if abs(dx) > abs(dy):
        return "EAST" if dx > 0 else "WEST"
    elif dy != 0:
        return "SOUTH" if dy > 0 else "NORTH"
    elif dx != 0:
        return "EAST" if dx > 0 else "WEST"
    return "PASS"

class WorkerManager(BaseManager):
    """Abstract base class for worker managers to allow swapping."""
    def initialize(self, context): pass
    def update(self, state, context): pass
    def plan(self, state, context): pass
    def execute(self, state, context): return {}

class HybridWorkerManager(WorkerManager):
    """
    V1 Scheduler (Unit-Centric Greedy) - Hybrid Baseline
    Iterates over each worker, assigning them the closest available task.
    Weeds are ignored (PASS).
    """
    def execute(self, state, context):
        my_farm = state.my_farm
        all_units = [my_farm.farmer] + list(my_farm.hands)
        
        unwatered_tiles = []
        harvestable_tiles = []
        empty_tiles = []
        weed_tiles = []
        
        max_melon_day = CROP_DATA["MELON"]["max_yield_day"]
        max_carrot_day = CROP_DATA["CARROT"]["max_yield_day"]
        
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                pos = Position(x=x, y=y)
                if tile.kind == "PLANT":
                    max_day = max_melon_day if tile.crop == "MELON" else max_carrot_day
                    if tile.planted_day is not None and (state.day - tile.planted_day) >= max_day:
                        harvestable_tiles.append(pos)
                    elif not tile.watered_today:
                        unwatered_tiles.append(pos)
                elif tile.kind == "WEED":
                    weed_tiles.append(pos)
                elif tile.is_empty():
                    empty_tiles.append(pos)
                    
        shed_tiles = [Position(x=x, y=y) for x, y in SHED_ADJACENT_TILES]
        targeted_tiles = set()
        unit_actions = []
        
        seed_reserves = {}
        
        for unit in all_units:
            # Priority 1: WATER
            valid_water = [p for p in unwatered_tiles if p not in targeted_tiles]
            if valid_water:
                target = min(valid_water, key=lambda p: _distance(unit.position, p))
                targeted_tiles.add(target)
                if unit.position == target:
                    action = ["WATER"]
                else:
                    action = [_choose_movement(unit.position, target)]
                unit_actions.append(action)
                continue
                
            # Priority 2: HARVEST
            valid_harvest = [p for p in harvestable_tiles if p not in targeted_tiles]
            if valid_harvest:
                target = min(valid_harvest, key=lambda p: _distance(unit.position, p))
                targeted_tiles.add(target)
                if unit.position == target:
                    action = ["HARVEST"]
                else:
                    action = [_choose_movement(unit.position, target)]
                unit_actions.append(action)
                continue
                
            # Priority 3: DROP
            has_produce = any(count > 0 for item, count in unit.inventory.items.items() if item != "FERTILIZER")
            if has_produce:
                target = min(shed_tiles, key=lambda p: _distance(unit.position, p))
                if unit.position in shed_tiles:
                    action = ["DROP"]
                else:
                    action = [_choose_movement(unit.position, target)]
                unit_actions.append(action)
                continue
                
            # Priority 4: PLANT
            valid_empty = [p for p in empty_tiles if p not in targeted_tiles]
            if valid_empty:
                best_seed_crop = "MELON" # Hardcoded to Melon for identical conservative strategy
                if my_farm.seeds and my_farm.seeds.get(best_seed_crop, 0) > seed_reserves.get(best_seed_crop, 0):
                    target = min(valid_empty, key=lambda p: _distance(unit.position, p))
                    targeted_tiles.add(target)
                    seed_reserves[best_seed_crop] = seed_reserves.get(best_seed_crop, 0) + 1
                    if unit.position == target:
                        action = ["PLANT", best_seed_crop]
                    else:
                        action = [_choose_movement(unit.position, target)]
                    unit_actions.append(action)
                    continue
                
            unit_actions.append(["PASS"])
            
        return {
            "farmer": unit_actions[0],
            "hands": unit_actions[1:]
        }

class HybridDigWorkerManager(WorkerManager):
    """
    V1 Scheduler (Unit-Centric Greedy) - Hybrid + DIG
    Iterates over each worker, assigning them the closest available task.
    Weeds are dug (DIG) with Priority 5.
    """
    def execute(self, state, context):
        my_farm = state.my_farm
        all_units = [my_farm.farmer] + list(my_farm.hands)
        
        unwatered_tiles = []
        harvestable_tiles = []
        empty_tiles = []
        weed_tiles = []
        
        max_melon_day = CROP_DATA["MELON"]["max_yield_day"]
        max_carrot_day = CROP_DATA["CARROT"]["max_yield_day"]
        
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                pos = Position(x=x, y=y)
                if tile.kind == "PLANT":
                    max_day = max_melon_day if tile.crop == "MELON" else max_carrot_day
                    if tile.planted_day is not None and (state.day - tile.planted_day) >= max_day:
                        harvestable_tiles.append(pos)
                    elif not tile.watered_today:
                        unwatered_tiles.append(pos)
                elif tile.kind == "WEED":
                    weed_tiles.append(pos)
                elif tile.is_empty():
                    empty_tiles.append(pos)
                    
        shed_tiles = [Position(x=x, y=y) for x, y in SHED_ADJACENT_TILES]
        targeted_tiles = set()
        unit_actions = []
        
        seed_reserves = {}
        
        for unit in all_units:
            # Priority 1: WATER
            valid_water = [p for p in unwatered_tiles if p not in targeted_tiles]
            if valid_water:
                target = min(valid_water, key=lambda p: _distance(unit.position, p))
                targeted_tiles.add(target)
                if unit.position == target:
                    action = ["WATER"]
                else:
                    action = [_choose_movement(unit.position, target)]
                unit_actions.append(action)
                continue
                
            # Priority 2: HARVEST
            valid_harvest = [p for p in harvestable_tiles if p not in targeted_tiles]
            if valid_harvest:
                target = min(valid_harvest, key=lambda p: _distance(unit.position, p))
                targeted_tiles.add(target)
                if unit.position == target:
                    action = ["HARVEST"]
                else:
                    action = [_choose_movement(unit.position, target)]
                unit_actions.append(action)
                continue
                
            # Priority 3: DROP
            has_produce = any(count > 0 for item, count in unit.inventory.items.items() if item != "FERTILIZER")
            if has_produce:
                target = min(shed_tiles, key=lambda p: _distance(unit.position, p))
                if unit.position in shed_tiles:
                    action = ["DROP"]
                else:
                    action = [_choose_movement(unit.position, target)]
                unit_actions.append(action)
                continue
                
            # Priority 4: PLANT
            valid_empty = [p for p in empty_tiles if p not in targeted_tiles]
            if valid_empty:
                best_seed_crop = "MELON" # Hardcoded to Melon for identical conservative strategy
                if my_farm.seeds and my_farm.seeds.get(best_seed_crop, 0) > seed_reserves.get(best_seed_crop, 0):
                    target = min(valid_empty, key=lambda p: _distance(unit.position, p))
                    targeted_tiles.add(target)
                    seed_reserves[best_seed_crop] = seed_reserves.get(best_seed_crop, 0) + 1
                    if unit.position == target:
                        action = ["PLANT", best_seed_crop]
                    else:
                        action = [_choose_movement(unit.position, target)]
                    unit_actions.append(action)
                    continue
                    
            # Priority 5: DIG Weeds
            valid_weeds = [p for p in weed_tiles if p not in targeted_tiles]
            if valid_weeds:
                target = min(valid_weeds, key=lambda p: _distance(unit.position, p))
                targeted_tiles.add(target)
                if unit.position == target:
                    action = ["DIG"]
                else:
                    action = [_choose_movement(unit.position, target)]
                unit_actions.append(action)
                continue
                
            unit_actions.append(["PASS"])
            
        return {
            "farmer": unit_actions[0],
            "hands": unit_actions[1:]
        }

class V2WorkerManager(WorkerManager):
    """
    V2 Scheduler (Tile-Centric Greedy)
    Iterates over each task priority list, finding the closest available worker.
    """
    def execute(self, state, context):
        my_farm = state.my_farm
        all_units = [my_farm.farmer] + list(my_farm.hands)
        available_units = list(all_units)
        
        unit_actions_map = {id(u): ["PASS"] for u in all_units}
        
        unwatered_tiles = []
        harvestable_tiles = []
        empty_tiles = []
        
        max_melon_day = CROP_DATA["MELON"]["max_yield_day"]
        max_carrot_day = CROP_DATA["CARROT"]["max_yield_day"]
        
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                pos = Position(x=x, y=y)
                if tile.kind == "PLANT":
                    max_day = max_melon_day if tile.crop == "MELON" else max_carrot_day
                    if tile.planted_day is not None and (state.day - tile.planted_day) >= max_day:
                        harvestable_tiles.append(pos)
                    elif not tile.watered_today:
                        unwatered_tiles.append(pos)
                elif tile.is_empty():
                    empty_tiles.append(pos)
                    
        shed_tiles = [Position(x=x, y=y) for x, y in SHED_ADJACENT_TILES]
        
        # Priority 1: WATER (Tile-centric)
        for target in unwatered_tiles:
            if not available_units: break
            best_unit = min(available_units, key=lambda u: _distance(u.position, target))
            if best_unit.position == target:
                unit_actions_map[id(best_unit)] = ["WATER"]
            else:
                unit_actions_map[id(best_unit)] = [_choose_movement(best_unit.position, target)]
            available_units.remove(best_unit)
            
        # Priority 2: HARVEST (Tile-centric)
        for target in harvestable_tiles:
            if not available_units: break
            best_unit = min(available_units, key=lambda u: _distance(u.position, target))
            if best_unit.position == target:
                unit_actions_map[id(best_unit)] = ["HARVEST"]
            else:
                unit_actions_map[id(best_unit)] = [_choose_movement(best_unit.position, target)]
            available_units.remove(best_unit)
            
        # Priority 3: DROP (Worker-centric because drop logic naturally hinges on worker inventory)
        drop_units = [u for u in available_units if any(c > 0 for i, c in u.inventory.items.items() if i != "FERTILIZER")]
        for u in drop_units:
            target = min(shed_tiles, key=lambda p: _distance(u.position, p))
            if u.position in shed_tiles:
                unit_actions_map[id(u)] = ["DROP"]
            else:
                unit_actions_map[id(u)] = [_choose_movement(u.position, target)]
            available_units.remove(u)
            
        # Priority 4: PLANT (Tile-centric)
        seed_reserves = 0
        best_seed_crop = "MELON"
        available_seeds = my_farm.seeds.get(best_seed_crop, 0) if my_farm.seeds else 0
        
        for target in empty_tiles:
            if not available_units: break
            if available_seeds - seed_reserves > 0:
                best_unit = min(available_units, key=lambda u: _distance(u.position, target))
                if best_unit.position == target:
                    unit_actions_map[id(best_unit)] = ["PLANT", best_seed_crop]
                else:
                    unit_actions_map[id(best_unit)] = [_choose_movement(best_unit.position, target)]
                available_units.remove(best_unit)
                seed_reserves += 1
                
        return {
            "farmer": unit_actions_map[id(my_farm.farmer)],
            "hands": [unit_actions_map[id(u)] for u in my_farm.hands]
        }