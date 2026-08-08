from fieldops.state import Position
from fieldops.managers.worker_manager import HybridWorkerManager, _distance, _choose_movement

class IntegratedWorkerManager(HybridWorkerManager):
    def discover_livestock_tasks(self, state):
        my_farm = state.my_farm
        tasks = [] # (pos, action_type, priority)

        # Feed (needs wheat)
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                if tile.has_animal() and not getattr(tile, 'fed_today', False):
                    tasks.append((Position(x, y), "FEED", 1000))
                    
        # CARE for sheep (Priority 40 in K4 means it yields to WATER Priority 60)
        unwatered_count = sum(1 for row in my_farm.tiles for t in row if getattr(t, 'kind', '') == "PLANT" and getattr(t, 'planted_day', None) is not None and not getattr(t, 'watered_today', False))
        if unwatered_count == 0:
            for y, row in enumerate(my_farm.tiles):
                for x, tile in enumerate(row):
                    if tile.has_animal() and tile.animal == "SHEEP":
                        if not getattr(tile, 'cared_today', False):
                            tasks.append((Position(x, y), "CARE", 40))
        
        # Fertilizer
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                if getattr(tile, 'has_fertilizer', False):
                    tasks.append((Position(x, y), "COLLECT_FERTILIZER", 85))
                    
        # Animal drops (Harvest animal)
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                if tile.is_harvestable() and tile.has_animal():
                    tasks.append((Position(x, y), "HARVEST", 85))

        # Feed (needs wheat)
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                if tile.has_animal() and not getattr(tile, 'fed_today', False):
                    tasks.append((Position(x, y), "FEED", 100))
                    
        # Building pastures / pickup / place (compact logic)
        animals_in_shed = []
        for anim in ["COW", "SHEEP"]:
            for _ in range(my_farm.shed.items.get(anim, 0)):
                animals_in_shed.append(anim)
                
        # Proactively build pastures if we need them! We check context.target_cows + context.target_sheep
        # wait, context doesn't have it. We can just set it on self in agent.
        target_animals = getattr(self, 'target_cows', 0) + getattr(self, 'target_sheep', 0)
        pastures_built = sum(1 for row in my_farm.tiles for t in row if t.kind == "PASTURE")
        
        empty_pastures = []
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                if tile.kind == "PASTURE" and not getattr(tile, 'has_animal', lambda: False)():
                    empty_pastures.append(Position(x, y))
                    
        if pastures_built < target_animals:
            # Build pasture!
            empty_tiles = [Position(x, y) for y, row in enumerate(my_farm.tiles) for x, tile in enumerate(row) if tile.is_empty()]
            if empty_tiles:
                best_pasture = min(empty_tiles, key=lambda p: abs(p.x - 4) + abs(p.y - 4))
                tasks.append((best_pasture, "BUILD_PASTURE", 95))
                
        if animals_in_shed and empty_pastures:
            tasks.append((Position(4, 4), f"PICKUP_{animals_in_shed[0]}", 95))

        return tasks

    def execute(self, state, context):
        base_actions = super().execute(state, context)
        
        my_farm = state.my_farm
        all_units = [my_farm.farmer] + list(my_farm.hands)
        
        final_actions = {"farmer": base_actions["farmer"], "hands": list(base_actions.get("hands", []))}
        livestock_tasks = self.discover_livestock_tasks(state)
        targeted = set()

        for i, unit in enumerate(all_units):
            action = None
            
            # Check if holding an animal
            held_animal = None
            for item in unit.inventory.items:
                if item in ["COW", "SHEEP"] and unit.inventory.items[item] > 0:
                    held_animal = item
                    break
                    
            if held_animal:
                empty_pastures = [Position(x, y) for y, row in enumerate(my_farm.tiles) for x, tile in enumerate(row) if tile.kind == "PASTURE" and not tile.has_animal()]
                if empty_pastures:
                    target = min(empty_pastures, key=lambda p: _distance(unit.position, p))
                    if unit.position == target:
                        action = ["PLACE", held_animal]
                    else:
                        action = [_choose_movement(unit.position, target)]
            else:
                # Need to feed? Must hold wheat.
                valid_tasks = [t for t in livestock_tasks if t[0] not in targeted]
                if valid_tasks:
                    # Score tasks: priority minus distance penalty
                    best_task = max(valid_tasks, key=lambda t: t[2] - _distance(unit.position, t[0])*2)
                    targeted.add(best_task[0])
                    target = best_task[0]
                    t_type = best_task[1]
                    
                    if unit.position == target:
                        if t_type.startswith("PICKUP_"):
                            action = ["PICKUP", t_type.split("_")[1]]
                        elif t_type == "FEED":
                            if unit.inventory.items.get("WHEAT", 0) > 0:
                                action = ["FEED"]
                            else:
                                if unit.position == Position(4, 4):
                                    action = ["PICKUP", "WHEAT"]
                                else:
                                    action = [_choose_movement(unit.position, Position(4, 4))]
                                    targeted.remove(target) # Didn't actually do the task yet
                        else:
                            action = [t_type]
                    else:
                        if t_type == "FEED" and unit.inventory.items.get("WHEAT", 0) == 0:
                            if unit.position == Position(4, 4):
                                action = ["PICKUP", "WHEAT"]
                            else:
                                action = [_choose_movement(unit.position, Position(4, 4))]
                            targeted.remove(target)
                        else:
                            action = [_choose_movement(unit.position, target)]

            # If livestock action determined, override the base crop action
            if action:
                if i == 0:
                    final_actions["farmer"] = action
                else:
                    final_actions["hands"][i-1] = action
                    
        return final_actions
