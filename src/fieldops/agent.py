"""
agent.py — FieldOps entry point.

This is the only file that Kaggle calls. It is intentionally thin:
all logic lives in state.py, planner.py, and executor.py.

The agent() function signature must match what Kaggle expects:
    def agent(obs: dict) -> dict

The returned dict must have the shape:
    {
        "farmer": [op, ...args],
        "hands":  [[op, ...args], ...],
        "market": [[op, ...args], ...],
    }
"""

import logging
import os
from typing import Any

from fieldops.state import ObservationParser, GameState, Position
from fieldops.constants import SHED_ADJACENT_TILES, CROP_DATA

logger = logging.getLogger(__name__)

# Optionally log useful debug information when DEBUG=True
DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "t")

def _log_debug_info(state: GameState) -> None:
    """Log useful debug information if DEBUG is enabled."""
    if not DEBUG:
        return

    my_farm = state.my_farm
    logger.info(
        f"Step: {state.step} | Day: {state.day} | Hour: {state.hour} | "
        f"Money: {my_farm.money} | "
        f"Farmer Pos: ({my_farm.farmer.position.x}, {my_farm.farmer.position.y})"
    )
    # Log inventory
    logger.info(f"Inventory: {dict(my_farm.farmer.inventory.items)}")

def _distance(p1: Position, p2: Position) -> int:
    return abs(p1.x - p2.x) + abs(p1.y - p2.y)

def _choose_movement(current: Position, target: Position) -> str:
    """Greedy Manhattan distance routing."""
    dx = target.x - current.x
    dy = target.y - current.y
    if abs(dx) > abs(dy):
        return "EAST" if dx > 0 else "WEST"
    elif dy != 0:
        return "SOUTH" if dy > 0 else "NORTH"
    elif dx != 0:
        return "EAST" if dx > 0 else "WEST"
    return "PASS"

class MiniMelonAgent:
    def __call__(self, obs: dict[str, Any]) -> dict[str, Any]:
        # 1. Parse observation
        state = ObservationParser.parse(obs)
        _log_debug_info(state)
        
        my_farm = state.my_farm
        
        actions = {
            "farmer": ["PASS"],
            "hands": [],
            "market": []
        }
        
        # 2. Market actions
        if len(my_farm.hands) == 0 and my_farm.money >= 1:
            actions["market"].append(["HIRE"])
            
        if my_farm.shed.get("MELON") > 0:
            actions["market"].append(["SELL", "MELON", my_farm.shed.get("MELON")])
            
        if state.step == 0:
            actions["market"].append(["BUY_SEED", "MELON", 12])
            
        # 3. Build target lists ONCE per turn
        max_yield_day = CROP_DATA["MELON"]["max_yield_day"]
        
        unwatered_tiles: list[Position] = []
        harvestable_tiles: list[Position] = []
        empty_tiles: list[Position] = []
        
        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                pos = Position(x=x, y=y)
                if tile.kind == "PLANT" and tile.crop == "MELON":
                    if tile.planted_day is not None and (state.day - tile.planted_day) >= max_yield_day:
                        harvestable_tiles.append(pos)
                    elif not tile.watered_today:
                        unwatered_tiles.append(pos)
                elif tile.is_empty():
                    empty_tiles.append(pos)
                    
        shed_tiles = [Position(x=x, y=y) for x, y in SHED_ADJACENT_TILES]
        
        all_units = [my_farm.farmer] + list(my_farm.hands)
        unit_actions = []
        targeted_tiles: set[Position] = set()
        
        seeds_available = my_farm.seeds.get("MELON", 0)
        seeds_reserved = 0
        
        for unit in all_units:
            # Priority 1: WATER urgent unwatered plants
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
                
            # Priority 2: HARVEST ready plants
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
                
            # Priority 3: DROP carried yield immediately
            if unit.inventory.items.get("MELON", 0) > 0:
                target = min(shed_tiles, key=lambda p: _distance(unit.position, p))
                if unit.position in shed_tiles:
                    action = ["DROP"]
                else:
                    action = [_choose_movement(unit.position, target)]
                unit_actions.append(action)
                continue
                
            # Priority 4: PLANT seeds in empty tiles
            if (seeds_available - seeds_reserved) > 0:
                valid_empty = [p for p in empty_tiles if p not in targeted_tiles]
                if valid_empty:
                    target = min(valid_empty, key=lambda p: _distance(unit.position, p))
                    targeted_tiles.add(target)
                    seeds_reserved += 1
                    if unit.position == target:
                        action = ["PLANT", "MELON"]
                    else:
                        action = [_choose_movement(unit.position, target)]
                    unit_actions.append(action)
                    continue
                    
            unit_actions.append(["PASS"])
            
        actions["farmer"] = unit_actions[0]
        actions["hands"] = unit_actions[1:]
        
        return actions

_agent_instance = MiniMelonAgent()

def agent(obs: dict[str, Any]) -> dict[str, Any]:
    """FieldOps agent entry point."""
    return _agent_instance(obs)
