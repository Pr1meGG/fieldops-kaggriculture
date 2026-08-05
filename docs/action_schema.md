# Action Schema

This document describes every valid action the agent can return each turn.
Derived from source code (`_apply_unit_action`, `_process_market`, `_parse_order`).

---

## Action Dict Format

```python
{
    "farmer": [op, ...args],          # one action for the main farmer
    "hands":  [[op, ...args], ...],   # one action per hired hand, in order
    "market": [[op, ...args], ...],   # ordered list of market orders
}
```

- Missing keys default to: `farmer=["PASS"]`, `hands=[]`, `market=[]`
- Extra market orders beyond `maxMarketOrdersPerTurn` (default 10) are silently dropped
- Invalid actions are **silent no-ops** — no error is raised
- Actions for hands that do not exist are ignored

---

## Farmer / Hand Actions

Each unit (farmer or hand) takes exactly one action per turn. All unit actions run simultaneously before market processing.

### `NORTH` / `SOUTH` / `EAST` / `WEST`

**Purpose**: Move one tile in the given direction.

| Parameter | None |
|---|---|
| Requirements | Target tile must be within board bounds (0 to boardSize-1) |
| Failure | Move off-board edge: silent no-op. Position unchanged. |
| Result | Unit position updated by (dx, dy): NORTH=(0,-1), SOUTH=(0,1), EAST=(1,0), WEST=(-1,0) |

**Important**: Movement onto LOCKED tiles is **allowed**. Units can cross locked quadrants. However, all tile actions (PLANT, WATER, BUILD_*, etc.) are no-ops while standing on a locked tile.

---

### `PASS`

**Purpose**: Do nothing this turn.

| Parameter | None |
|---|---|
| Requirements | None |
| Failure | Cannot fail |
| Result | No change |

Default action if `farmer` key is missing or action is invalid.

---

### `PLANT <crop>`

**Purpose**: Plant a seed on the current tile.

| Parameter | `crop` — one of `WHEAT`, `CARROT`, `TOMATO`, `STRAWBERRY`, `MELON` |
|---|---|
| Requirements | Standing on an empty (`None`) unlocked tile; at least 1 seed of that crop in `private["seeds"]` |
| Failure conditions | Tile is not None; tile is LOCKED; no seeds available; crop not in CROPS; multi-unit conflict (see below) |
| Result | Tile becomes a plant dict; `private["seeds"][crop]` decremented by 1 |

**Multi-unit PLANT validation**: If the combined count of PLANT requests for a crop across ALL units this turn exceeds the seed count, **all** PLANT actions for that crop are converted to PASS. Neither unit plants.

**Critical detail**: A newly planted crop starts with `consecutive_unwatered = 1`. The planting day counts as an unwatered day. If not watered on the planting day and also not watered the next day, `consecutive_unwatered` reaches 2 at end-of-day and the crop becomes a weed before it ever grows.

---

### `WATER`

**Purpose**: Water the plant on the current tile.

| Parameter | None |
|---|---|
| Requirements | Standing on a plant tile (`kind == "PLANT"`); plant not already watered today |
| Failure conditions | Not a plant tile; `watered_today` is already True |
| Result | `watered_today = True`; yield bonus may apply (see below) |

**Yield bonus for one-time crops** (WHEAT, CARROT, MELON):
```
window_start = ceil(max_yield_day / 2)   # i.e. (max_yield_day + 1) // 2
if window_start <= age_days <= max_yield_day:
    bonus = 2 if fertilized else 1
    yield_units = min(max_yield, yield_units + bonus)
```

| Crop | window_start | max_yield_day | Bonus window (age in days) |
|---|---|---|---|
| WHEAT | 2 | 4 | days 2-4 |
| CARROT | 2 | 3 | days 2-3 |
| MELON | 6 | 12 | days 6-12 |

**No yield bonus for ongoing crops** (TOMATO, STRAWBERRY) from WATER. Their yield is determined at end-of-day by the fertilizer+watering check.

Watering does not stack. Calling WATER twice on the same plant on the same day: the second call is a no-op.

---

### `HARVEST`

**Purpose**: Collect produce from a plant or animal on the current tile.

| Parameter | None |
|---|---|
| Requirements | Standing on a plant or animal tile with `yield_units > 0`; crop age >= `first_yield_day` |
| Failure conditions | Not a plant/animal tile; `yield_units == 0`; crop age < `first_yield_day` |
| Result | Items added to unit's inventory; `yield_units` reset to 0; one-time crop tile cleared to None |

**One-time crops**: tile becomes `None` after harvest (tile is freed for replanting).

**Ongoing crops**: tile remains as a plant. The crop will continue yielding on schedule.

**Animals**: tile remains as the animal structure. Animal continues producing.

**Harvest goes to inventory** (not shed directly). Items in inventory are only accessible from the shed after end-of-day drop, or manually via DROP/PLACE.

---

### `FERTILIZE`

**Purpose**: Apply fertilizer to a plant to increase yields.

| Parameter | None |
|---|---|
| Requirements | Standing on a plant tile (`kind == "PLANT"`); unit has at least 1 FERTILIZER in inventory |
| Failure conditions | Not a plant tile; no FERTILIZER in inventory |
| Result | 1 FERTILIZER consumed from inventory; `fertilized_until_day = max(current, day + 2)` |

The fertilizer bonus is active for days: `current_day`, `current_day + 1`, `current_day + 2` (3 days inclusive).

Multiple FERTILIZE calls stack by taking the maximum: calling again on day 3 when `fertilized_until_day = 5` sets it to `max(5, 3+2) = 5` (no change in this case, but calling on day 4 would extend to day 6).

**Effect on one-time crops**: watering within the bonus window adds 2 yield_units instead of 1.
**Effect on ongoing crops**: if both fertilized and watered on a scheduled production day, yield is 2 instead of 1 (applied at end-of-day).

---

### `DIG`

**Purpose**: Remove a plant, weed, or empty structure from the current tile.

| Parameter | None |
|---|---|
| Requirements | Standing on a non-None tile |
| Failure conditions | Tile is None; tile is a coop/pasture with an animal on it |
| Result | Tile becomes None |

Can remove: plants (any age, even with yield_units), weeds, empty coops, empty pastures.
Cannot remove: animal structures that have a placed animal (`"animal" in tile`).

Removing a plant discards all `yield_units` — no produce is collected.

---

### `BUILD_COOP`

**Purpose**: Build a goose coop on the current tile.

| Parameter | None |
|---|---|
| Requirements | Standing on an empty (`None`) unlocked tile |
| Failure conditions | Tile is not None; tile is LOCKED |
| Result | Tile becomes `{"kind": "COOP"}` |

Cost: **free** (no money deducted). The cost of housing is only the tile space.

After building, a goose can be PLACEd here. Until then, the tile is an empty COOP with no animal.

---

### `BUILD_PASTURE`

**Purpose**: Build a cow/sheep pasture on the current tile.

| Parameter | None |
|---|---|
| Requirements | Standing on an empty (`None`) unlocked tile |
| Failure conditions | Tile is not None; tile is LOCKED |
| Result | Tile becomes `{"kind": "PASTURE"}` |

Same rules as BUILD_COOP. Cows and sheep both use PASTURE structures.

---

### `FEED`

**Purpose**: Feed the animal on the current tile.

| Parameter | None |
|---|---|
| Requirements | Standing on an animal tile (`"animal" in tile`); unit has at least 1 WHEAT in inventory; animal not already fed today |
| Failure conditions | Not an animal tile; no WHEAT in inventory; `fed_today` is already True |
| Result | 1 WHEAT consumed from unit inventory; `fed_today = True` |

WHEAT must be in the **unit's own inventory**, not in the shed. The farmer must PICKUP WHEAT from the shed first (or buy it via BUY_PRODUCT and have it arrive in the shed, then pick it up).

---

### `CARE`

**Purpose**: Care for the animal on the current tile (banks a yield bonus).

| Parameter | None |
|---|---|
| Requirements | Standing on an animal tile; `cared_today` is False |
| Failure conditions | Not an animal tile; already cared today |
| Result | `cared_today = True`; no items consumed |

CARE is free (no items consumed). At end-of-day, if the animal was BOTH fed AND cared, `pending_care_bonus += 1`. The bonus is paid out on the next scheduled production day if the animal is fed that day.

---

### `COLLECT_FERTILIZER`

**Purpose**: Collect 1 fertilizer unit produced by an animal.

| Parameter | None |
|---|---|
| Requirements | Standing on an animal tile; `fertilizer_available` is True |
| Failure conditions | Not an animal tile; `fertilizer_available` is False |
| Result | `fertilizer_available = False`; 1 FERTILIZER added to unit inventory |

Every surviving animal generates 1 fertilizer per day, set at end-of-day (`fertilizer_available = True`). Uncollected fertilizer does NOT accumulate — leaving it for 5 days still only gives 1 unit when collected.

---

### `PICKUP <item> [n]`

**Purpose**: Move items from the shed into unit inventory.

| Parameter | `item` — any key in `private["shed"]`; `n` — quantity (default 1) |
|---|---|
| Requirements | Unit must be shed-adjacent (standing on one of the 4 center tiles) |
| Failure conditions | Not shed-adjacent; item not in shed or count is 0 |
| Result | Up to `n` units of `item` moved from shed to unit inventory |

Seeds cannot be picked up with PICKUP — they live in `private["seeds"]` and are consumed directly by PLANT.

Shed-adjacent tiles (boardSize=10): `(4,4)`, `(5,4)`, `(4,5)`, `(5,5)`.

---

### `DROP`

**Purpose**: Dump the unit's entire inventory into the shed.

| Parameter | None |
|---|---|
| Requirements | Unit must be shed-adjacent |
| Failure conditions | Not shed-adjacent |
| Result | All inventory items moved to shed up to `shedCapacity`; overflow discarded; inventory cleared |

DROP dumps everything, not a selective amount. Overflow is permanently lost.

---

### `PLACE <item> [n]`

**Purpose**: Place an animal on a structure, or drop items into the shed.

**Variant 1 — Animal placement**:

| Parameter | `item` — animal name (`GOOSE`, `COW`, `SHEEP`) |
|---|---|
| Requirements | Standing on a matching empty structure (GOOSE on COOP, COW/SHEEP on PASTURE); unit has the animal in inventory |
| Failure conditions | Not on matching structure; structure already has an animal; animal not in inventory |
| Result | 1 animal consumed from inventory; tile becomes full animal tile |

**Variant 2 — Shed drop** (when shed-adjacent):

| Parameter | `item` — any item name; `n` — quantity (default 1) |
|---|---|
| Requirements | Unit must be shed-adjacent; item in unit inventory |
| Failure conditions | Not shed-adjacent; item not in inventory; shed full |
| Result | Up to `n` units moved from inventory to shed; shed cap enforced |

The interpreter tries animal placement first; if that fails, it tries shed drop.

---

## Market Actions

Market actions are in `obs["market"]` — a list of orders processed in submission order. Up to `maxMarketOrdersPerTurn` orders are processed (default 10).

All market actions use the same item names as the rest of the game.

---

### `["BUY_SEED", crop, n]`

**Purpose**: Purchase `n` seeds of `crop` from the market at a fixed price.

| Parameter | `crop` — crop name; `n` — integer quantity |
|---|---|
| Requirements | Sufficient money; valid crop name; n > 0 |
| Failure conditions | Insufficient money (order stops mid-way); invalid crop |
| Price | Fixed: WHEAT=10, CARROT=20, TOMATO=50, STRAWBERRY=100, MELON=80 |
| Result | Money deducted; seeds added to `private["seeds"]`; market inventory NOT affected |

Seeds do not come from market inventory. Seed supply is unlimited. Seeds land directly in `private["seeds"]`.

---

### `["BUY_PRODUCT", item, n]`

**Purpose**: Purchase `n` units of `item` from the market at the current dynamic price.

| Parameter | `item` — must be `WHEAT` or `FERTILIZER` only; `n` — integer quantity |
|---|---|
| Requirements | Sufficient money; shed not full; item must be WHEAT or FERTILIZER |
| Failure conditions | Insufficient money; shed full; item is not WHEAT or FERTILIZER |
| Price | Dynamic (post-buy inventory quoted: `market_price(item, inventory - 1)`) |
| Result | Money deducted; item added to shed; market inventory decremented |

Only WHEAT and FERTILIZER can be bought from the market. All other products can be sold but not bought back.

Items land in the **shed** (not farmer inventory).

---

### `["BUY_ANIMAL", animal, n]`

**Purpose**: Purchase `n` animals from the market.

| Parameter | `animal` — `GOOSE`, `COW`, or `SHEEP`; `n` — integer quantity |
|---|---|
| Requirements | Sufficient money; shed not full; valid animal name |
| Failure conditions | Insufficient money; shed full; invalid animal name |
| Price | Fixed: GOOSE=300, COW=400, SHEEP=500 |
| Result | Money deducted; animal added to shed (`private["shed"]["GOOSE"]`, etc.) |

Animals land in the shed and must be manually moved to inventory via PICKUP, then PLACEd on a matching structure.

---

### `["SELL", item, n]`

**Purpose**: Sell `n` units of `item` from the shed at the current dynamic price.

| Parameter | `item` — any item in PRODUCTS; `n` — integer quantity |
|---|---|
| Requirements | Item present in shed in sufficient quantity; valid item name |
| Failure conditions | Item not in shed or count is 0 (order stops) |
| Price | Dynamic (pre-sell inventory quoted: `market_price(item, current_inventory)`) |
| Result | Item removed from shed; money added; market inventory incremented (unless price == $1) |

**Price floor rule**: if the price is $1, the item is still sold (player receives $1), but it is NOT added back to market inventory. The floor stays at $1 but inventory does not grow further.

Both players sell simultaneously, one unit at a time, quoting the same pre-commit inventory. Large sell orders from both players simultaneously crash the price faster than one player selling alone.

---

### `["HIRE"]`

**Purpose**: Hire a farm hand for the current day.

| Parameter | None |
|---|---|
| Requirements | Sufficient money |
| Failure conditions | Insufficient money |
| Cost | `farmHandCostMult * fib(hires_today)` — Fibonacci: 1, 1, 2, 3, 5, 8, 13, ... |
| Result | Money deducted; new hand spawned at a shed-adjacent tile; hand added to `farm["hands"]` |

Hire is atomic: processed before SELL/BUY orders in the same turn. Cost increases for each hire on the same day and resets at end-of-day.

The hand spawns at the shed-adjacent tile with the lowest current occupant count (NWSE tie-break). The first hand of each day typically spawns at (5,4) — the NE shed-access tile, which is LOCKED until NE is purchased.

---

### `["BUY_LAND"]`

**Purpose**: Unlock the next farm quadrant.

| Parameter | None |
|---|---|
| Requirements | Sufficient money; not all quadrants already unlocked |
| Failure conditions | Insufficient money; already 4 quadrants unlocked |
| Cost | First buy=$1000 (NE), second=$2000 (SW), third=$4000 (SE) |
| Result | Money deducted; next quadrant (NE→SW→SE) unlocked; those tiles set to None |

BUY_LAND is atomic: processed before SELL/BUY orders. Quadrants unlock in fixed order: NE, SW, SE (regardless of which order you might want them).

---

## Action Failure Summary

All invalid actions are **silent no-ops**. The game does not error or penalize for invalid actions. However, a wasted action costs you the turn.

| Common mistake | Result |
|---|---|
| PLANT with no seeds | No-op |
| PLANT while 2 units compete for 1 seed | Both no-op |
| WATER on a non-plant tile | No-op |
| HARVEST with yield_units == 0 | No-op |
| HARVEST before first_yield_day | No-op |
| FEED with no WHEAT in inventory | No-op |
| PICKUP when not shed-adjacent | No-op |
| BUY_PRODUCT with shed full | No-op (order stops) |
| SELL with item not in shed | No-op (order stops) |
| BUY_LAND with insufficient money | No-op |
| Market order with n <= 0 | Parsed as None, skipped |
| Market order with missing n | Parsed as None, skipped |
