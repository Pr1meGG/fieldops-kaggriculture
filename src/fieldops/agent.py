"""
agent.py — FieldOps Stage 1 Aggressive Expansion Agent.

Implements:
- Continuous production cycles (MELON -> CARROT fast finish).
- Dynamic land expansion (BUY_LAND for NE, SW, SE quadrants when cash permits).
- Dynamic workforce scaling (hires hands up to target count based on unlocked land).
- Dynamic continuous seed purchasing (re-orders seeds for all empty unlocked tiles).
- Single-pass target list unit scheduling (HARVEST -> WATER -> DROP -> PLANT).
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
        f"Money: ${my_farm.money:,.2f} | Quadrants: {my_farm.unlocked_quadrants}"
    )

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
        
        # -------------------------------------------------------------------
        # 1. Market Logic: Selling, Land Purchase, Hiring, Seed Purchase
        # -------------------------------------------------------------------
        
        # A. Sell all harvested products sitting in shed
        if my_farm.shed is not None:
            for item, count in my_farm.shed.items.items():
                if count > 0 and item != "FERTILIZER":
                    actions["market"].append(["SELL", item, count])
                    
        # B. Dynamic Land Purchase Policy
        # Quadrants: 1 (NW unlocked), 2 ($1k), 3 ($2k), 4 ($4k)
        quads_unlocked = len(my_farm.unlocked_quadrants)
        if quads_unlocked < 4:
            land_cost = 1000 if quads_unlocked == 1 else (2000 if quads_unlocked == 2 else 4000)
            seed_buffer = 25 * CROP_DATA["MELON"]["seed_cost"]  # $2,000
            worker_buffer = 100
            
            # Buy land if cash >= land_cost + seed_buffer + worker_buffer AND remaining day <= 18
            if my_farm.money >= (land_cost + seed_buffer + worker_buffer) and state.day <= 18:
                actions["market"].append(["BUY_LAND"])
                
        # C. Dynamic Workforce Scaling
        # Scale daily hires with unlocked land based on the PROVEN Phase 1 optimum of 14 tiles per worker.
        total_tiles = quads_unlocked * 25
        target_hands = (total_tiles // 14) - 1
        target_hands = max(0, target_hands)
        if my_farm.hires_today < target_hands and my_farm.money >= 50:
            actions["market"].append(["HIRE"])
            
        # D. Dynamic Continuous Seed Purchasing
        empty_unlocked_tiles = [
            Position(x=x, y=y)
            for y, row in enumerate(my_farm.tiles)
            for x, tile in enumerate(row)
            if tile.is_empty()
        ]
        num_empty = len(empty_unlocked_tiles)
        
        # Select target crop based on remaining time window and expected profit
        best_crop = None
        best_profit = -1
        
        for crop_name, data in CROP_DATA.items():
            if state.day + data["max_yield_day"] <= 29:
                profit = data["base_price"] * data["max_yield_unf"] - data["seed_cost"]
                if profit > best_profit:
                    best_profit = profit
                    best_crop = crop_name
                    
        target_crop = best_crop
        
        if target_crop is not None and num_empty > 0:
            # Count how many seeds we already have that can still mature
            usable_seeds = 0
            if my_farm.seeds:
                for c_name, count in my_farm.seeds.items():
                    if state.day + CROP_DATA[c_name]["max_yield_day"] <= 29:
                        usable_seeds += count
            
            target_buffer = min(num_empty, 8)
            needed_seeds = target_buffer - usable_seeds
            
            if needed_seeds > 0:
                seed_cost = CROP_DATA[target_crop]["seed_cost"]
                buy_qty = min(needed_seeds, int(my_farm.money // seed_cost))
                if buy_qty > 0:
                    actions["market"].append(["BUY_SEED", target_crop, buy_qty])

        # -------------------------------------------------------------------
        # 2. Single-Pass Target Lists & Unit Scheduler
        # -------------------------------------------------------------------
        max_melon_day = CROP_DATA["MELON"]["max_yield_day"]
        max_carrot_day = CROP_DATA["CARROT"]["max_yield_day"]
        
        unwatered_tiles: list[Position] = []
        harvestable_tiles: list[Position] = []
        empty_tiles: list[Position] = []
        
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
        all_units = [my_farm.farmer] + list(my_farm.hands)
        unit_actions = []
        targeted_tiles: set[Position] = set()
        
        seed_reserves = {}
        
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
                
            # Priority 3: DROP carried produce immediately
            has_produce = any(count > 0 for item, count in unit.inventory.items.items() if item != "FERTILIZER")
            if has_produce:
                target = min(shed_tiles, key=lambda p: _distance(unit.position, p))
                if unit.position in shed_tiles:
                    action = ["DROP"]
                else:
                    action = [_choose_movement(unit.position, target)]
                unit_actions.append(action)
                continue
                
            # Priority 4: PLANT available seeds into empty tiles
            valid_empty = [p for p in empty_tiles if p not in targeted_tiles]
            if valid_empty:
                best_seed_crop = None
                best_seed_profit = -1
                
                if my_farm.seeds:
                    for crop_name, count in my_farm.seeds.items():
                        reserved = seed_reserves.get(crop_name, 0)
                        if count - reserved > 0:
                            data = CROP_DATA.get(crop_name)
                            if data and state.day + data["max_yield_day"] <= 29:
                                profit = data["base_price"] * data["max_yield_unf"] - data["seed_cost"]
                                if profit > best_seed_profit:
                                    best_seed_profit = profit
                                    best_seed_crop = crop_name
                                    
                if best_seed_crop is not None:
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
            
        actions["farmer"] = unit_actions[0]
        actions["hands"] = unit_actions[1:]
        
        return actions

_agent_instance = MiniMelonAgent()

def agent(obs: dict[str, Any]) -> dict[str, Any]:
    """FieldOps entry point."""
    return _agent_instance(obs)
