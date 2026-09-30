"""strategy.py — Deterministic strategy decision layer.

Decides the agent's *market* and *crop* intent each turn from the parsed
GameState. It does NOT schedule worker movement (that stays in
worker_manager.py) and it does NOT emit farmer/hand actions.

Pure functions, no RNG, no LLM. Unit-testable in isolation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fieldops.state import GameState
from fieldops import constants as C


@dataclass(frozen=True)
class StrategyConfig:
    """Tunable parameters for the decision layer (defaults = conservative)."""
    cash_reserve: int = 250             # minimum cash kept before spending
    max_hires: int = 3                  # hard ceiling on concurrent hands
    task_mult: float = 1.4              # hired when pending_tasks/units exceeds this
    target_crops: int = 20              # target number of planted crop tiles
    seeds_reorder_at: int = 2           # replant when fewer than this many seeds on hand
    sell_when_price_below: int = 1      # always sell (matches champion); set >1 to hold


@dataclass
class StrategyDecisions:
    market: list[list[Any]] = field(default_factory=list)  # market order lists
    crop: str = "MELON"                                     # crop to plant this turn


def _fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return max(a, 1)


def _pending_task_estimate(state: GameState) -> int:
    """Approximate outstanding water+harvest units this turn."""
    tasks = 0
    for row in state.my_farm.tiles:
        for t in row:
            if t.is_plant():
                if not t.watered_today:
                    tasks += 1
                elif t.is_harvestable():
                    tasks += 1
    return tasks


def _choose_crop(state: GameState) -> str:
    """Pick a crop that matures before season end, preferring MELON.

    The repo's own validated experiments (EXP-001/003) show MELON dominates on
    first-yield efficiency; it stays the choice whenever it matures in time.
    Late in the season we fall back to the best still-maturing crop so we never
    buy seeds we cannot harvest. Returns "" when nothing matures before end.
    """
    days_left = C.TOTAL_DAYS - state.day
    if days_left < 2:
        return ""
    # MELON is the proven best while it matures in time.
    if days_left >= C.CROP_DATA["MELON"]["first_yield_day"]:
        return "MELON"
    # Late game: best (value per day-to-first-yield) maturing crop.
    best, best_score = "", -1.0
    for crop, meta in C.CROP_DATA.items():
        if crop == "MELON":
            continue
        first = meta["first_yield_day"]
        if days_left < first:
            continue
        eff = meta["max_yield_unf"] * meta["base_price"] / max(1, first)
        if eff > best_score:
            best, best_score = crop, eff
    return best


def _hire_decision(state: GameState, cfg: StrategyConfig) -> list[list[Any]]:
    """Add a hand when pending tasks exceed current capacity and cash allows."""
    current_units = 1 + len(state.my_farm.hands)
    pending = _pending_task_estimate(state)
    # Cost of the next hire today: fibonacci-indexed by hires_today.
    hire_idx = state.my_farm.hires_today
    cost = _fib(hire_idx) * C.FARM_HAND_COST_MULT
    if len(state.my_farm.hands) == 0 and state.day == 0:
        # always secure the first hand (proven champion setup)
        if state.my_farm.money - cost >= cfg.cash_reserve:
            return [["HIRE"]]
    if pending > current_units * cfg.task_mult and len(state.my_farm.hands) < cfg.max_hires:
        if state.my_farm.money - cost - cfg.seeds_reorder_at * C.CROP_DATA["WHEAT"]["seed_cost"] >= cfg.cash_reserve:
            return [["HIRE"]]
    return []


def _buy_seeds(state: GameState, crop: str, cfg: StrategyConfig) -> list[list[Any]]:
    """Buy seeds toward the target crop count, clipped by money/order budget."""
    if not crop:
        return []
    farm = state.my_farm
    planted = sum(1 for row in farm.tiles for t in row if t.is_plant())
    on_hand = farm.seeds.get(crop, 0) if farm.seeds else 0
    need = max(0, cfg.target_crops - planted - on_hand)
    if need <= 0:
        return []
    cost = C.CROP_DATA[crop]["seed_cost"]
    affordable = (farm.money - cfg.cash_reserve) // cost if cost > 0 else 0
    qty = min(need, max(0, affordable))
    if qty > 0:
        return [["BUY_SEED", crop, qty]]
    return []


def _sell_all(state: GameState, cfg: StrategyConfig) -> list[list[Any]]:
    """Liquidate non-fertilizer shed produce. Optionally hold a crop below a
    price floor (disabled by default to match champion's always-sell)."""
    orders: list[list[Any]] = []
    if not state.my_farm.shed:
        return orders
    hold = set() if cfg.sell_when_price_below <= 1 else set()
    for item, count in sorted(state.my_farm.shed.items.items()):
        if count <= 0 or item == "FERTILIZER" or item in hold:
            continue
        orders.append(["SELL", item, count])
    return orders


def decide(state: GameState, config: StrategyConfig | None = None) -> StrategyDecisions:
    """Main strategy entry point. Returns market orders + chosen crop."""
    cfg = config or StrategyConfig()
    dec = StrategyDecisions()

    dec.crop = _choose_crop(state)

    # Priority order: liquidate -> hire -> buy seeds (leave cash reserve).
    dec.market.extend(_sell_all(state, cfg))
    if dec.crop:
        dec.market.extend(_hire_decision(state, cfg))
        dec.market.extend(_buy_seeds(state, dec.crop, cfg))

    # Hard cap on market orders per turn (game limit), keep the most valuable.
    if len(dec.market) > C.MAX_MARKET_ORDERS_PER_TURN:
        dec.market = dec.market[:C.MAX_MARKET_ORDERS_PER_TURN]
    return dec
