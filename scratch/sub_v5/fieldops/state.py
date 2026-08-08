"""
state.py — Observation parser and typed game state.

WHY THIS FILE EXISTS:
    The raw Kaggriculture observation is an untyped nested dict. Tile values
    can be None, "LOCKED", or a variety of dicts with different keys depending
    on tile kind. Working with raw dicts everywhere is fragile.

    This module parses the raw dict into typed Python dataclasses once per turn.
    Every other module in FieldOps works with these typed objects — none touch
    the raw dict directly.

    If the observation schema ever changes, this is the only file to update.

DESIGN DECISIONS:
    - Single Tile dataclass with optional fields (no polymorphic hierarchy yet).
      Predicate methods (is_plant(), is_animal(), etc.) make tile kind explicit.
    - ObservationParser.parse() is the sole entry point. Validation happens here.
    - All dataclasses are frozen (immutable) — each turn produces a fresh snapshot.
    - CROP_DATA and ANIMAL_DATA remain in constants.py; no runtime domain objects.
"""

from __future__ import annotations

import types
from dataclasses import dataclass
from typing import Any

from fieldops.constants import (
    BOARD_SIZE,
    TOTAL_TURNS,
    TURNS_PER_DAY,
)


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Position:
    """Immutable 2D coordinate on the farm grid.

    Coordinates: x = column (0 = leftmost), y = row (0 = top).
    Both axes run 0 to BOARD_SIZE - 1 (default 0–9).
    """

    x: int
    y: int


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Inventory:
    """Immutable collection of item counts.

    Used for: farmer/hand carried items, shed contents, seeds, market stock.

    The `items` dict maps item name → non-negative count.
    The `items` dict maps item name → non-negative count.
    The dict is wrapped in a MappingProxyType to guarantee deep immutability.
    """

    items: types.MappingProxyType[str, int]

    def __init__(self, items: dict[str, int] | None = None) -> None:
        if items is None:
            items = {}
        object.__setattr__(self, "items", types.MappingProxyType(items))

    def get(self, item: str) -> int:
        """Return the count of `item` (0 if absent)."""
        return self.items.get(item, 0)

    def has(self, item: str, n: int = 1) -> bool:
        """Return True if `item` count is at least `n`."""
        return self.items.get(item, 0) >= n

    def total(self) -> int:
        """Return the sum of all item counts."""
        return sum(self.items.values())


# ---------------------------------------------------------------------------
# Farmer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Farmer:
    """Main farmer unit on the field.

    Position resets to (4, 4) at end-of-day.
    Inventory is dropped to the shed at end-of-day and cleared.
    """

    position: Position
    inventory: Inventory


# ---------------------------------------------------------------------------
# Hand
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Hand:
    """One hired farm hand.

    `index` is 0-based; corresponds to private["inventories"][1 + index].
    All hands are removed at end-of-day. Inventories are dropped to shed.
    """

    index: int
    position: Position
    inventory: Inventory


# ---------------------------------------------------------------------------
# Tile
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Tile:
    """One cell of the 10x10 farm grid.

    `kind` determines which optional fields are populated:
      None          — empty unlocked tile (all optional fields are None)
      "LOCKED"      — tile in a quadrant the player has not purchased
      "PLANT"       — growing or harvestable crop
      "WEED"        — obstructed tile; must DIG before reuse
      "COOP"        — goose housing (may or may not have an animal)
      "PASTURE"     — cow/sheep housing (may or may not have an animal)

    Use the predicate methods to check tile kind rather than comparing
    `kind` strings directly. This makes planner code easier to read and
    localises the string constants.

    Note on optional fields: accessing, e.g., tile.crop on a WEED tile
    returns None. Always call is_plant() before accessing plant-specific fields.
    """

    x: int
    y: int

    # Tile discriminator. None means empty (unlocked, unoccupied).
    kind: str | None = None

    # --- Plant fields (kind == "PLANT") ---
    crop: str | None = None                   # "WHEAT", "CARROT", etc.
    planted_day: int | None = None
    watered_today: bool | None = None
    consecutive_unwatered: int | None = None
    yield_units: int | None = None            # also used for animal tiles
    max_lifespan_step: int | None = None      # -1 for ongoing crops
    fertilized_until_day: int | None = None   # -1 if not fertilized

    # --- Animal structure fields (kind in ("COOP", "PASTURE")) ---
    # Note: animal-specific fields (placed_day, fed_today, etc.) are None
    # if the structure is empty (animal is None).
    animal: str | None = None                 # "GOOSE", "COW", "SHEEP", or None
    placed_day: int | None = None
    fed_today: bool | None = None
    consecutive_unfed: int | None = None
    cared_today: bool | None = None
    fertilizer_available: bool | None = None
    pending_care_bonus: int | None = None

    # --- Predicates ---

    def is_empty(self) -> bool:
        """True if this tile is unlocked and unoccupied."""
        return self.kind is None

    def is_locked(self) -> bool:
        """True if this tile is in a quadrant the player has not purchased."""
        return self.kind == "LOCKED"

    def is_plant(self) -> bool:
        """True if this tile has a growing or harvestable crop."""
        return self.kind == "PLANT"

    def is_weed(self) -> bool:
        """True if this tile is blocked by a weed."""
        return self.kind == "WEED"

    def is_animal(self) -> bool:
        """True if this tile is an animal structure (COOP or PASTURE)."""
        return self.kind in ("COOP", "PASTURE")

    def has_animal(self) -> bool:
        """True if this tile is an animal structure with a placed animal."""
        return self.is_animal() and self.animal is not None

    def is_harvestable(self) -> bool:
        """True if this tile has yield_units > 0 (plant or animal)."""
        return self.yield_units is not None and self.yield_units > 0


# ---------------------------------------------------------------------------
# FarmState
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FarmState:
    """Complete state snapshot for one player's farm.

    Both farms are publicly visible (tiles, farmer, hands, money, quadrants).
    The private fields (shed, seeds) are only populated for the agent's own farm.
    For the opponent's farm, shed and seeds are None.

    tiles[y][x] — row-major indexing, matching the raw observation layout.

    To check if this is the agent's own farm: `farm.shed is not None`.
    """

    player_index: int
    money: float
    tiles: tuple[tuple[Tile, ...], ...] # tiles[y][x], 10x10
    farmer: Farmer
    hands: tuple[Hand, ...]
    unlocked_quadrants: list[str]       # subset of ["NW", "NE", "SW", "SE"]
    hires_today: int

    # Private fields — None for the opponent's farm.
    shed: Inventory | None
    seeds: dict[str, int] | None        # {"WHEAT": 3, "CARROT": 0, ...}


# ---------------------------------------------------------------------------
# MarketState
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MarketState:
    """Shared market state — visible to both players.

    `inventory` can go negative (town consumes even when stock is 0).
    `prices` are floored at $1 and reflect end state of the previous turn.
    """

    inventory: dict[str, int]   # {"WHEAT": 9800, ...}
    prices: dict[str, int]      # {"WHEAT": 25, ...}


# ---------------------------------------------------------------------------
# TownState
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TownState:
    """Shared town state — visible to both players.

    Shops unlock at end-of-day when (day + 1) % townShopUnlockInterval == 0.
    Once unlocked, a shop never locks again.
    Shops drain market inventory on fixed intervals, which raises sell prices.
    """

    unlocked_shops: list[str]   # ["BAKERY", "PET_CAFE", ...]


# ---------------------------------------------------------------------------
# GameState
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GameState:
    """Complete immutable snapshot of the game at the start of a turn.

    Produced once per turn by ObservationParser.parse().
    All other modules receive this object and must not modify it.

    Lifetime: turn-scoped. Discarded when agent() returns.
    """

    step: int           # 0 to TOTAL_TURNS - 2 (agent never sees the final step)
    day: int            # step // TURNS_PER_DAY (0–29)
    hour: int           # step % TURNS_PER_DAY (0–23)
    player_index: int   # agent's own player ID (0 or 1)

    my_farm: FarmState
    opponent_farm: FarmState
    market: MarketState
    town: TownState


# ---------------------------------------------------------------------------
# ObservationParser
# ---------------------------------------------------------------------------


class ObservationParser:
    """Stateless parser that converts a raw Kaggle observation dict into a GameState.

    Entry point: ObservationParser.parse(obs)

    Validation is performed at parse time. A ValueError with a descriptive
    message is raised if any invariant is violated. Downstream modules can
    trust their inputs.
    """

    @staticmethod
    def parse(obs: dict[str, Any]) -> GameState:
        """Parse the raw Kaggriculture observation into a typed GameState.

        Args:
            obs: Raw observation dict from the environment.

        Returns:
            A fully typed, immutable GameState snapshot.

        Raises:
            ValueError: If any structural invariant is violated.
            KeyError: If the observation is missing an expected field (schema change).
        """
        step: int = obs["step"]
        day: int = obs["day"]
        hour: int = obs["hour"]
        player_index: int = obs["player"]

        _validate_time(step, day, hour)

        raw_farms = obs["farms"]
        raw_private = obs["private"]
        raw_market = obs["market"]
        raw_town = obs["town"]

        my_farm = _parse_farm(raw_farms[player_index], player_index, raw_private)
        opponent_index = 1 - player_index
        opponent_farm = _parse_farm(raw_farms[opponent_index], opponent_index, private=None)

        market = _parse_market(raw_market)
        town = _parse_town(raw_town)

        return GameState(
            step=step,
            day=day,
            hour=hour,
            player_index=player_index,
            my_farm=my_farm,
            opponent_farm=opponent_farm,
            market=market,
            town=town,
        )


# ---------------------------------------------------------------------------
# Internal parse helpers
# ---------------------------------------------------------------------------


def _validate_time(step: int, day: int, hour: int) -> None:
    """Validate step, day, and hour consistency."""
    max_step = TOTAL_TURNS - 2
    if not (0 <= step <= max_step):
        raise ValueError(
            f"step {step!r} is out of range [0, {max_step}]"
        )
    expected_day = step // TURNS_PER_DAY
    if day != expected_day:
        raise ValueError(
            f"day {day!r} is inconsistent with step {step}: expected {expected_day}"
        )
    expected_hour = step % TURNS_PER_DAY
    if hour != expected_hour:
        raise ValueError(
            f"hour {hour!r} is inconsistent with step {step}: expected {expected_hour}"
        )


def _validate_position(x: int, y: int, label: str) -> None:
    """Validate that a coordinate pair is within the board bounds."""
    if not (0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE):
        raise ValueError(
            f"{label} position ({x}, {y}) is out of board bounds "
            f"[0, {BOARD_SIZE - 1}]"
        )


def _validate_inventory_counts(inv: dict[str, int], label: str) -> None:
    """Validate that all item counts in an inventory dict are non-negative."""
    for item, count in inv.items():
        if count < 0:
            raise ValueError(
                f"{label} inventory has negative count {count!r} for item {item!r}"
            )


def _parse_farm(
    raw: dict[str, Any],
    player_index: int,
    private: dict[str, Any] | None,
) -> FarmState:
    """Parse one farm dict into a FarmState.

    Args:
        raw: The raw farm dict from obs["farms"][p].
        player_index: The player index this farm belongs to.
        private: obs["private"] for the own farm; None for the opponent's farm.
    """
    money: float = raw["money"]
    if money < 0:
        raise ValueError(f"farm[{player_index}].money is negative: {money!r}")

    raw_tiles: list[list[Any]] = raw["tiles"]
    if len(raw_tiles) != BOARD_SIZE:
        raise ValueError(
            f"farm[{player_index}].tiles has {len(raw_tiles)} rows, expected {BOARD_SIZE}"
        )
    tiles: list[list[Tile]] = []
    for y, row in enumerate(raw_tiles):
        if len(row) != BOARD_SIZE:
            raise ValueError(
                f"farm[{player_index}].tiles[{y}] has {len(row)} cols, expected {BOARD_SIZE}"
            )
        tiles.append([_parse_tile(raw_tile, x, y, player_index) for x, raw_tile in enumerate(row)])

    raw_farmer_pos: list[int] = raw["farmer"]
    if len(raw_farmer_pos) < 2:
        raise ValueError(
            f"farm[{player_index}].farmer position is malformed: {raw_farmer_pos!r}"
        )
    fx, fy = raw_farmer_pos[0], raw_farmer_pos[1]
    _validate_position(fx, fy, f"farm[{player_index}].farmer")

    raw_hands: list[list[int]] = raw["hands"]
    unlocked_quadrants: list[str] = raw["unlocked_quadrants"]
    hires_today: int = raw["hires_today"]

    if "NW" not in unlocked_quadrants:
        raise ValueError(
            f"farm[{player_index}].unlocked_quadrants missing 'NW': {unlocked_quadrants!r}"
        )

    shed: Inventory | None = None
    seeds: dict[str, int] | None = None

    if private is not None:
        # Own farm: parse private state.
        raw_inventories: list[dict[str, int]] = private["inventories"]
        n_hands = len(raw_hands)
        expected_inv_count = 1 + n_hands  # farmer + one per hand
        if len(raw_inventories) != expected_inv_count:
            raise ValueError(
                f"farm[{player_index}]: private.inventories has {len(raw_inventories)} entries "
                f"but expected {expected_inv_count} (1 farmer + {n_hands} hands)"
            )

        raw_shed: dict[str, int] = private["shed"]
        _validate_inventory_counts(raw_shed, f"farm[{player_index}].shed")
        shed = Inventory(items=dict(raw_shed))

        raw_seeds: dict[str, int] = private["seeds"]
        _validate_inventory_counts(raw_seeds, f"farm[{player_index}].seeds")
        seeds = dict(raw_seeds)

        raw_farmer_inv = raw_inventories[0]
        _validate_inventory_counts(raw_farmer_inv, f"farm[{player_index}].farmer.inventory")
        farmer_inv = Inventory(items=dict(raw_farmer_inv))

        hands: list[Hand] = []
        for i, raw_pos in enumerate(raw_hands):
            if len(raw_pos) < 2:
                raise ValueError(
                    f"farm[{player_index}].hands[{i}] position is malformed: {raw_pos!r}"
                )
            hx, hy = raw_pos[0], raw_pos[1]
            _validate_position(hx, hy, f"farm[{player_index}].hands[{i}]")
            raw_hand_inv = raw_inventories[1 + i]
            _validate_inventory_counts(raw_hand_inv, f"farm[{player_index}].hands[{i}].inventory")
            hands.append(Hand(
                index=i,
                position=Position(hx, hy),
                inventory=Inventory(items=dict(raw_hand_inv)),
            ))
    else:
        # Opponent farm: no private data; inventories are unknown.
        farmer_inv = Inventory(items={})
        hands = []
        for i, raw_pos in enumerate(raw_hands):
            if len(raw_pos) < 2:
                raise ValueError(
                    f"farm[{player_index}].hands[{i}] position is malformed: {raw_pos!r}"
                )
            hx, hy = raw_pos[0], raw_pos[1]
            _validate_position(hx, hy, f"farm[{player_index}].hands[{i}]")
            hands.append(Hand(
                index=i,
                position=Position(hx, hy),
                inventory=Inventory(items={}),
            ))

    farmer = Farmer(
        position=Position(fx, fy),
        inventory=farmer_inv,
    )

    return FarmState(
        player_index=player_index,
        money=money,
        tiles=tuple(tuple(row) for row in tiles),
        farmer=farmer,
        hands=tuple(hands),
        unlocked_quadrants=list(unlocked_quadrants),
        hires_today=hires_today,
        shed=shed,
        seeds=seeds,
    )


def _parse_tile(raw: Any, x: int, y: int, farm_index: int) -> Tile:
    """Convert one raw tile value into a typed Tile.

    Args:
        raw: The raw tile value from obs["farms"][p]["tiles"][y][x].
             Can be None, "LOCKED", or a dict.
        x: Column index.
        y: Row index.
        farm_index: Player index (for error messages only).

    Returns:
        A typed Tile.
    """
    if raw is None:
        return Tile(x=x, y=y, kind=None)

    if raw == "LOCKED":
        return Tile(x=x, y=y, kind="LOCKED")

    if not isinstance(raw, dict):
        raise ValueError(
            f"farm[{farm_index}].tiles[{y}][{x}]: unexpected tile value {raw!r}"
        )

    kind: str = raw["kind"]

    if kind == "WEED":
        return Tile(x=x, y=y, kind="WEED")

    if kind == "PLANT":
        return Tile(
            x=x,
            y=y,
            kind="PLANT",
            crop=raw["crop"],
            planted_day=raw["planted_day"],
            watered_today=raw["watered_today"],
            consecutive_unwatered=raw["consecutive_unwatered"],
            yield_units=raw["yield_units"],
            max_lifespan_step=raw["max_lifespan_step"],
            fertilized_until_day=raw["fertilized_until_day"],
        )

    if kind in ("COOP", "PASTURE"):
        # "animal" key is absent from empty structures; present when occupied.
        animal: str | None = raw.get("animal")
        has_animal = animal is not None
        return Tile(
            x=x,
            y=y,
            kind=kind,
            animal=animal,
            placed_day=raw.get("placed_day") if has_animal else None,
            yield_units=raw.get("yield_units", 0),
            fed_today=raw.get("fed_today") if has_animal else None,
            consecutive_unfed=raw.get("consecutive_unfed") if has_animal else None,
            cared_today=raw.get("cared_today") if has_animal else None,
            fertilizer_available=raw.get("fertilizer_available") if has_animal else None,
            pending_care_bonus=raw.get("pending_care_bonus") if has_animal else None,
        )

    raise ValueError(
        f"farm[{farm_index}].tiles[{y}][{x}]: unknown tile kind {kind!r}"
    )


def _parse_market(raw: dict[str, Any]) -> MarketState:
    """Parse the raw market dict into a MarketState."""
    return MarketState(
        inventory=dict(raw["inventory"]),
        prices=dict(raw["prices"]),
    )


def _parse_town(raw: dict[str, Any]) -> TownState:
    """Parse the raw town dict into a TownState."""
    return TownState(
        unlocked_shops=list(raw["unlocked_shops"]),
    )
