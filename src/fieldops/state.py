"""
state.py — Observation parser.

WHY THIS FILE EXISTS:
    The raw Kaggriculture observation is an untyped nested dict. Tile values
    can be None, "LOCKED", or a variety of dicts with different keys.

    This module parses that raw dict into typed Python dataclasses once per
    turn. Every other module in FieldOps works with these typed objects,
    never with raw dicts.

    Benefits:
    - Autocomplete and type checking work properly
    - Defensive None checks are centralized here, not scattered everywhere
    - If the observation schema changes, this is the only file to update

STATUS: stub — dataclasses are defined but parse() is not yet implemented.
    This will be fully implemented in Phase 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Tile types
# ---------------------------------------------------------------------------

@dataclass
class EmptyTile:
    """An unlocked, unoccupied tile."""
    x: int
    y: int


@dataclass
class LockedTile:
    """A tile in a quadrant the player has not yet purchased."""
    x: int
    y: int


@dataclass
class WeedTile:
    """A tile overgrown with a weed. Must be cleared with DIG before use."""
    x: int
    y: int


@dataclass
class PlantTile:
    """A tile with a growing or harvestable crop."""
    x: int
    y: int
    crop: str                   # e.g. "WHEAT", "CARROT"
    planted_day: int
    watered_today: bool
    consecutive_unwatered: int
    yield_units: int            # units ready to harvest right now
    max_lifespan_step: int      # step at which decay begins; -1 for ongoing
    fertilized_until_day: int   # -1 if not fertilized


@dataclass
class AnimalTile:
    """A tile with a coop or pasture, optionally occupied by an animal."""
    x: int
    y: int
    structure: str              # "COOP" or "PASTURE"
    animal: str | None          # "GOOSE", "COW", "SHEEP", or None
    placed_day: int
    yield_units: int
    fed_today: bool
    consecutive_unfed: int
    cared_today: bool
    fertilizer_available: bool
    pending_care_bonus: int


# A tile is one of these five types.
Tile = EmptyTile | LockedTile | WeedTile | PlantTile | AnimalTile


# ---------------------------------------------------------------------------
# Farm state (one per player, both visible to both players)
# ---------------------------------------------------------------------------

@dataclass
class FarmState:
    """Public state for one player's farm."""
    player_index: int
    money: float
    tiles: list[list[Tile]]             # tiles[y][x]
    farmer_pos: tuple[int, int]         # (x, y)
    hand_positions: list[tuple[int, int]]
    unlocked_quadrants: list[str]       # subset of ["NW", "NE", "SW", "SE"]
    hires_today: int


# ---------------------------------------------------------------------------
# Private state (only visible to the current player)
# ---------------------------------------------------------------------------

@dataclass
class PrivateState:
    """Private state for the current player only."""
    shed: dict[str, int]               # {"WHEAT": 5, "EGG": 2, ...}
    seeds: dict[str, int]              # {"WHEAT": 3, "CARROT": 1, ...}
    inventories: list[dict[str, int]]  # [farmer_inv, hand1_inv, ...]


# ---------------------------------------------------------------------------
# Market state (shared, visible to both players)
# ---------------------------------------------------------------------------

@dataclass
class MarketState:
    """Shared market state."""
    inventory: dict[str, int]   # {"WHEAT": 9800, ...}
    prices: dict[str, int]      # {"WHEAT": 25, ...}


# ---------------------------------------------------------------------------
# Town state (shared)
# ---------------------------------------------------------------------------

@dataclass
class TownState:
    """Shared town state."""
    unlocked_shops: list[str]   # ["BAKERY", "PET_CAFE", ...]


# ---------------------------------------------------------------------------
# Full game state (produced once per turn)
# ---------------------------------------------------------------------------

@dataclass
class GameState:
    """
    Complete typed snapshot of the game at the current turn.

    Produced by parse() from the raw observation dict.
    All other modules consume this object; none touch the raw dict.
    """
    player_index: int
    day: int
    hour: int                   # turn within the day (0–23)
    step: int                   # absolute turn number (0–719)
    my_farm: FarmState
    opponent_farm: FarmState
    private: PrivateState
    market: MarketState
    town: TownState


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse(obs: dict[str, Any]) -> GameState:
    """
    Parse the raw Kaggriculture observation into a typed GameState.

    Args:
        obs: Raw observation dict from the environment.

    Returns:
        A fully typed GameState.

    Raises:
        KeyError: If the observation is missing expected fields.
            This should not happen with a valid environment, but if it does,
            it means the observation schema has changed.
    """
    # TODO: implement in Phase 1
    raise NotImplementedError(
        "state.parse() is not yet implemented. "
        "This will be built in Phase 1."
    )


def _parse_tile(raw: Any, x: int, y: int) -> Tile:
    """
    Convert a single raw tile value into a typed Tile.

    Args:
        raw: The raw tile value from obs["farms"][p]["tiles"][y][x].
             Can be None, "LOCKED", or a dict.
        x: Column index.
        y: Row index.

    Returns:
        The appropriate Tile subtype.
    """
    # TODO: implement in Phase 1
    raise NotImplementedError("_parse_tile() is not yet implemented.")
