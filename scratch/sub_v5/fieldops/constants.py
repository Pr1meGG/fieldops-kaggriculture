"""
constants.py — All Kaggriculture game constants.

WHY THIS FILE EXISTS:
    Every numeric value in this file comes directly from the competition rules.
    By centralizing them here, no raw integers appear in strategy or execution
    logic. This makes the code readable ("TURNS_PER_DAY" vs "24") and safe to
    maintain (change once, applies everywhere).

    If a game configuration value ever changes, this is the only file to update.

IMPORTANT:
    These are the *default* competition values. Some can be overridden by the
    environment configuration. For now we optimize against the defaults.
"""

# ---------------------------------------------------------------------------
# Season structure
# ---------------------------------------------------------------------------

TURNS_PER_DAY: int = 24
TOTAL_DAYS: int = 30
TOTAL_TURNS: int = TURNS_PER_DAY * TOTAL_DAYS  # 720

# ---------------------------------------------------------------------------
# Economy
# ---------------------------------------------------------------------------

STARTING_MONEY: int = 3_000
SHED_CAPACITY: int = 100          # max non-seed items in the shed
MAX_MARKET_ORDERS_PER_TURN: int = 10

# ---------------------------------------------------------------------------
# Farm layout
# ---------------------------------------------------------------------------

BOARD_SIZE: int = 10              # 10×10 grid, each player
QUADRANT_SIZE: int = 5            # each quadrant is 5×5 tiles
TILES_PER_QUADRANT: int = QUADRANT_SIZE * QUADRANT_SIZE  # 25

# Land purchase costs (NE, SW, SE order, but we track by cost tier)
LAND_COST_TIER_1: int = 1_000    # first additional quadrant
LAND_COST_TIER_2: int = 2_000    # second additional quadrant
LAND_COST_TIER_3: int = 4_000    # third additional quadrant

# ---------------------------------------------------------------------------
# Shed adjacency (tiles considered "adjacent" to the shed)
# At boardSize=10, half=5; shed-adjacent tiles are (4,4),(5,4),(4,5),(5,5)
# ---------------------------------------------------------------------------

BOARD_HALF: int = BOARD_SIZE // 2
SHED_ADJACENT_TILES: list[tuple[int, int]] = [
    (BOARD_HALF - 1, BOARD_HALF - 1),  # (4, 4)
    (BOARD_HALF,     BOARD_HALF - 1),  # (5, 4)
    (BOARD_HALF - 1, BOARD_HALF),      # (4, 5)
    (BOARD_HALF,     BOARD_HALF),      # (5, 5)
]

# ---------------------------------------------------------------------------
# Weed spawning
# ---------------------------------------------------------------------------

WEED_SPAWN_CHANCE: float = 0.005   # per empty unlocked tile, per end-of-day

# ---------------------------------------------------------------------------
# Farm hands
# ---------------------------------------------------------------------------

FARM_HAND_COST_MULT: int = 1  # cost = farmHandCostMult * fib(n)
# Fibonacci sequence for hire costs: 1, 1, 2, 3, 5, 8, 13, 21, ...
# Index 0 = first hire today, index 1 = second hire, etc.

# ---------------------------------------------------------------------------
# Town
# ---------------------------------------------------------------------------

TOWN_SHOP_UNLOCK_INTERVAL_DAYS: int = 3    # new shop every N days
TOWN_SHOP_SELL_INTERVAL_TURNS: int = 4     # shop consumes product every N turns
TOWN_CENTER_SELL_INTERVAL_TURNS: int = 12  # town center consumes every N turns
TOWN_CENTER_SCALE_DAY_1: int = 10          # demand doubles after this day
TOWN_CENTER_SCALE_DAY_2: int = 20          # demand quadruples after this day

# ---------------------------------------------------------------------------
# Crop metadata
# ---------------------------------------------------------------------------
# Keys match the crop names used in the observation ("WHEAT", "CARROT", etc.)
#
# Fields:
#   seed_cost         — market price to buy one seed
#   base_price        — base sell price at market equilibrium
#   yield_type        — "one_time" or "ongoing"
#   first_yield_day   — days after planting before first harvest is available
#   max_yield_day     — days after planting at which yield stops increasing
#   max_yield         — maximum harvestable units (watered + fertilized)
#   max_yield_unf     — maximum without fertilizer (watered only)
#   action_cost       — farmer actions consumed to manage this crop per cycle
#   subsequent_yields — None for one-time; description for ongoing

CROP_DATA: dict[str, dict] = {
    "WHEAT": {
        "seed_cost": 10,
        "base_price": 25,
        "yield_type": "one_time",
        "first_yield_day": 2,
        "max_yield_day": 4,
        "max_yield": 6,         # with fertilizer
        "max_yield_unf": 4,     # without fertilizer (watered only)
        "action_cost": 1,
        "subsequent_yields": None,
    },
    "CARROT": {
        "seed_cost": 20,
        "base_price": 35,
        "yield_type": "one_time",
        "first_yield_day": 2,
        "max_yield_day": 3,
        "max_yield": 4,
        "max_yield_unf": 3,
        "action_cost": 1,
        "subsequent_yields": None,
    },
    "TOMATO": {
        "seed_cost": 50,
        "base_price": 60,
        "yield_type": "ongoing",
        "first_yield_day": 8,
        "max_yield_day": 11,    # all 4 scheduled yields fire by day 11
        "max_yield": 4,         # total scheduled productions (then decays)
        "max_yield_unf": 4,
        "action_cost": 1,
        "subsequent_yields": "every day ×4",
    },
    "STRAWBERRY": {
        "seed_cost": 100,
        "base_price": 120,
        "yield_type": "ongoing",
        "first_yield_day": 10,
        "max_yield_day": 16,    # yields at days 10, 12, 14, 16
        "max_yield": 4,
        "max_yield_unf": 4,
        "action_cost": 1,
        "subsequent_yields": "every other day ×4",
    },
    "MELON": {
        "seed_cost": 80,
        "base_price": 250,
        "yield_type": "one_time",
        "first_yield_day": 10,
        "max_yield_day": 12,
        "max_yield": 6,
        "max_yield_unf": 6,
        "action_cost": 1,
        "subsequent_yields": None,
    },
}

# ---------------------------------------------------------------------------
# Animal metadata
# ---------------------------------------------------------------------------
# Fields:
#   purchase_cost   — market price for one animal
#   product         — what it produces
#   base_price      — base sell price of the product
#   structure       — "COOP" or "PASTURE"
#   structure_cost  — additional cost to build the structure (one action)
#   feed_cost_per_day — wheat consumed daily (1 per animal)
#   first_yield_day — days after placement before first production
#   yield_interval  — days between subsequent productions (1=daily, 2=every other, etc.)
#   max_held        — max unharvested product units on the tile

ANIMAL_DATA: dict[str, dict] = {
    "GOOSE": {
        "purchase_cost": 300,
        "product": "EGG",
        "base_price": 50,
        "structure": "COOP",
        "structure_cost": 1,      # one build action
        "feed_cost_per_day": 1,   # 1 wheat/day
        "first_yield_day": 4,
        "yield_interval": 1,      # produces every day
        "max_held": 4,
    },
    "COW": {
        "purchase_cost": 400,
        "product": "MILK",
        "base_price": 160,
        "structure": "PASTURE",
        "structure_cost": 1,
        "feed_cost_per_day": 1,
        "first_yield_day": 8,
        "yield_interval": 2,      # produces every 2 days
        "max_held": 6,
    },
    "SHEEP": {
        "purchase_cost": 500,
        "product": "WOOL",
        "base_price": 200,
        "structure": "PASTURE",
        "structure_cost": 1,
        "feed_cost_per_day": 1,
        "first_yield_day": 6,
        "yield_interval": 3,      # produces every 3 days
        "max_held": 6,
    },
}

# ---------------------------------------------------------------------------
# Market starting inventory (I0)
# ---------------------------------------------------------------------------

MARKET_I0: int = 10_000   # starting inventory for every product

# ---------------------------------------------------------------------------
# Tile kinds (as they appear in the observation)
# ---------------------------------------------------------------------------

TILE_KIND_PLANT: str = "PLANT"
TILE_KIND_WEED: str = "WEED"
TILE_KIND_COOP: str = "COOP"
TILE_KIND_PASTURE: str = "PASTURE"
TILE_LOCKED: str = "LOCKED"

# ---------------------------------------------------------------------------
# Farmer actions (as strings used in the action dict)
# ---------------------------------------------------------------------------

ACTION_NORTH: str = "NORTH"
ACTION_SOUTH: str = "SOUTH"
ACTION_EAST: str = "EAST"
ACTION_WEST: str = "WEST"
ACTION_PASS: str = "PASS"
ACTION_PLANT: str = "PLANT"
ACTION_WATER: str = "WATER"
ACTION_HARVEST: str = "HARVEST"
ACTION_FERTILIZE: str = "FERTILIZE"
ACTION_FEED: str = "FEED"
ACTION_CARE: str = "CARE"
ACTION_COLLECT_FERTILIZER: str = "COLLECT_FERTILIZER"
ACTION_BUILD_COOP: str = "BUILD_COOP"
ACTION_BUILD_PASTURE: str = "BUILD_PASTURE"
ACTION_DIG: str = "DIG"
ACTION_PICKUP: str = "PICKUP"
ACTION_PLACE: str = "PLACE"
ACTION_DROP: str = "DROP"

# ---------------------------------------------------------------------------
# Market order types
# ---------------------------------------------------------------------------

MARKET_BUY_SEED: str = "BUY_SEED"
MARKET_BUY_PRODUCT: str = "BUY_PRODUCT"
MARKET_BUY_ANIMAL: str = "BUY_ANIMAL"
MARKET_SELL: str = "SELL"
MARKET_HIRE: str = "HIRE"
MARKET_BUY_LAND: str = "BUY_LAND"

# ---------------------------------------------------------------------------
# Quadrant names
# ---------------------------------------------------------------------------

QUADRANT_NW: str = "NW"
QUADRANT_NE: str = "NE"
QUADRANT_SW: str = "SW"
QUADRANT_SE: str = "SE"

QUADRANT_ORDER: list[str] = [QUADRANT_NW, QUADRANT_NE, QUADRANT_SW, QUADRANT_SE]
