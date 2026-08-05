# Observation Schema

This document describes every field in the observation dict passed to the agent each turn.
Derived from source code (`kaggriculture.py`, `kaggriculture.json`) and live experiments.

The observation is a dict-like object. All fields documented below are confirmed present at step 0.

---

## Top-Level Fields

Confirmed top-level keys (verified by experiment):
```
remainingOverageTime, step, player, farms, private, market, town, day, hour
```

---

### `step`

| Property | Value |
|---|---|
| Type | `int` |
| Visibility | Present in obs (injected by framework, not the interpreter) |
| Range | `0` to `episodeSteps - 2` (agent never sees the final step) |
| Changes | Every turn |

The absolute turn number, 0-indexed. With default settings: 0–718.

**Important**: This is the step the agent is being asked to act on. It is NOT the step that was just processed.

---

### `day`

| Property | Value |
|---|---|
| Type | `int` |
| Visibility | Shared (both players see the same value) |
| Range | `0` to `29` |
| Formula | `step // turnsPerDay` |
| Changes | At start of each new day |

The current in-game day, 0-indexed. Day 0 is the first day.

---

### `hour`

| Property | Value |
|---|---|
| Type | `int` |
| Visibility | Shared |
| Range | `0` to `turnsPerDay - 1` (default: 0–23) |
| Formula | `step % turnsPerDay` |
| Changes | Every turn |

The current turn within the day, 0-indexed. Hour 0 is the first turn of the day.

---

### `player`

| Property | Value |
|---|---|
| Type | `int` |
| Visibility | Per-agent (each player sees their own index) |
| Possible values | `0` or `1` |
| Changes | Never (constant throughout game) |

The agent's own player index. Use `obs["farms"][obs["player"]]` to access your own farm.

---

### `remainingOverageTime`

| Property | Value |
|---|---|
| Type | `int` or `float` |
| Visibility | Per-agent |
| Default | `60` (from JSON schema) |

Time budget for agent responses. Managed by the framework. The `actTimeout` in the JSON is `1` second per turn.

---

## `farms`

A list of two farm dicts, indexed by player ID. Both farms are **publicly visible** to both players. Opponent's farm tiles are fully visible; opponent's shed and inventories are not.

```python
obs["farms"][0]   # Player 0's farm
obs["farms"][1]   # Player 1's farm
obs["farms"][obs["player"]]   # Your farm
```

---

### `farms[p]["money"]`

| Property | Value |
|---|---|
| Type | `float` |
| Visibility | Public (both players can see both players' money) |
| Initial value | `3000.0` |
| Changes | After market transactions, hiring, land purchases |

Current bank balance. Can go below zero in theory if the interpreter allowed it (in practice, transactions are refused if money is insufficient).

---

### `farms[p]["tiles"]`

| Property | Value |
|---|---|
| Type | `list[list[tile]]` — a 2D array |
| Visibility | Public |
| Indexing | `tiles[y][x]` — y is row (0=top), x is column (0=left) |
| Size | `boardSize x boardSize` (default 10x10) |

Each `tile` is one of:

#### `None`
Empty, unlocked tile. Can be planted, built on, or spawned by weeds.

#### `"LOCKED"`
Tile in a quadrant the player has not yet purchased. Movement is allowed across locked tiles. All other actions (PLANT, WATER, BUILD_*, etc.) are **silent no-ops** on locked tiles.

#### Plant tile (dict)

```python
{
    "kind":                 "PLANT",
    "crop":                 str,    # "WHEAT"|"CARROT"|"TOMATO"|"STRAWBERRY"|"MELON"
    "planted_day":          int,    # day on which PLANT was called
    "watered_today":        bool,   # True if WATER called since last end-of-day reset
    "consecutive_unwatered": int,   # days since last watering; starts at 1 (planting counts)
    "yield_units":          int,    # units currently ready to harvest
    "max_lifespan_step":    int,    # step at which decay begins; -1 for ongoing until final yield fires
    "fertilized_until_day": int,    # last day the fertilizer bonus applies; -1 if never fertilized
}
```

Field details:

| Field | Changes when |
|---|---|
| `watered_today` | Set True by WATER action; reset to False at end-of-day |
| `consecutive_unwatered` | Incremented each end-of-day the plant was NOT watered; reset to 0 when watered |
| `yield_units` | Increases during yield window on WATER; reset to 0 on HARVEST; decremented during decay |
| `max_lifespan_step` | Set at creation (one-time crops); set when final ongoing yield fires |
| `fertilized_until_day` | Set to `current_day + 2` on FERTILIZE (inclusive); stacks by taking max |

**Weed conversion**: if `consecutive_unwatered >= 2` at end-of-day, the plant tile becomes `{"kind": "WEED"}`.

#### Weed tile (dict)

```python
{"kind": "WEED"}
```

Blocks the tile. Must be removed with DIG before the tile can be reused. No other fields.

#### Animal structure tile (dict)

```python
{
    "kind":                 "COOP" | "PASTURE",
    "animal":               str | None,    # "GOOSE"|"COW"|"SHEEP", or None (empty structure)
    "placed_day":           int,           # day on which animal was PLACEd
    "yield_units":          int,           # unharvested product units on this tile
    "fed_today":            bool,          # True if FEED called since last end-of-day reset
    "consecutive_unfed":    int,           # days since last feeding (starts at 0)
    "cared_today":          bool,          # True if CARE called since last end-of-day reset
    "fertilizer_available": bool,          # True if uncollected fertilizer is ready
    "pending_care_bonus":   int,           # accumulated bonus from CARE, paid on next yield
}
```

**Note**: `animal` is absent (not `None`) from an empty structure dict (one that was built but has no animal yet). Check with `"animal" in tile` rather than `tile["animal"] is not None`.

Wait — from source `_new_animal`:
```python
{"kind": a["structure"], "animal": animal, ...}
```
And from `BUILD_COOP`:
```python
{"kind": "COOP"}   # no "animal" key
```

So an **empty structure** has no `"animal"` key. A **placed animal** has `"animal": "GOOSE"` etc.
**Always check**: `isinstance(tile, dict) and "animal" in tile` to confirm a tile has a placed animal.

Field details:

| Field | Changes when |
|---|---|
| `animal` | Set to animal name on PLACE; removed (entire tile becomes bare structure) if animal escapes |
| `yield_units` | Incremented at end-of-day on scheduled production; reset to 0 on HARVEST; capped at `max_held` |
| `fed_today` | Set True by FEED action (consuming 1 WHEAT from farmer inventory); reset at end-of-day |
| `consecutive_unfed` | Incremented each end-of-day if not fed; reset to 0 if fed |
| `cared_today` | Set True by CARE action (free, no items consumed); reset at end-of-day |
| `fertilizer_available` | Set True at end-of-day for every surviving animal; cleared by COLLECT_FERTILIZER |
| `pending_care_bonus` | Incremented +1 at end-of-day if both fed AND cared; consumed on next yield day; reset to 0 |

**Animal escape**: if `consecutive_unfed >= 2` at end-of-day, animal is removed. The structure tile remains as `{"kind": "COOP"}` or `{"kind": "PASTURE"}` — the building is not lost.

---

### `farms[p]["farmer"]`

| Property | Value |
|---|---|
| Type | `[int, int]` — `[x, y]` |
| Visibility | Public |
| Initial value | `[4, 4]` |
| Changes | On movement actions; resets to `[4, 4]` each end-of-day |

The main farmer's position. x=column, y=row. Y increases downward.

---

### `farms[p]["hands"]`

| Property | Value |
|---|---|
| Type | `list[list[int]]` — list of `[x, y]` positions |
| Visibility | Public |
| Initial value | `[]` |
| Changes | On HIRE (appends); on movement; reset to `[]` each end-of-day |

Positions of all currently hired farm hands. Index 0 = first hand hired today. Corresponds to `obs["private"]["inventories"][1]`, `[2]`, etc.

---

### `farms[p]["unlocked_quadrants"]`

| Property | Value |
|---|---|
| Type | `list[str]` |
| Visibility | Public |
| Initial value | `["NW"]` |
| Possible values | Subset of `["NW", "NE", "SW", "SE"]` |
| Changes | When BUY_LAND is processed |

The NW quadrant is always unlocked. Additional quadrants are unlocked via BUY_LAND in order: NE ($1000), SW ($2000), SE ($4000).

---

### `farms[p]["hires_today"]`

| Property | Value |
|---|---|
| Type | `int` |
| Visibility | Public |
| Initial value | `0` |
| Range | `0` to however many hands have been hired this day |
| Changes | Incremented each time HIRE succeeds; reset to 0 each end-of-day |

Number of hands hired so far today. The cost of the NEXT hire is `farmHandCostMult * fib(hires_today)`.

Fibonacci sequence (0-indexed): fib(0)=1, fib(1)=1, fib(2)=2, fib(3)=3, fib(4)=5, fib(5)=8, ...

---

## `private`

Per-agent. Only visible to the player whose observation it is. The opponent's private state is not accessible.

---

### `private["shed"]`

| Property | Value |
|---|---|
| Type | `dict[str, int]` |
| Visibility | Private |
| Initial value | All products and animals at 0 |

Keys present at initialization (always present, even when 0):
```python
["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
 "EGG", "MILK", "WOOL", "FERTILIZER",
 "GOOSE", "COW", "SHEEP"]
```

This means animals in the shed are stored here (e.g. `shed["GOOSE"] = 1`) until placed on a tile. The shed capacity of 100 applies to the **total** of all non-seed values in this dict.

---

### `private["seeds"]`

| Property | Value |
|---|---|
| Type | `dict[str, int]` |
| Visibility | Private |
| Initial value | All crops at 0 |

Keys: `["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]`

Seeds do NOT count toward shed capacity. They are consumed directly by the PLANT action. They are never in the shed dict. There is no cap on seed count.

---

### `private["inventories"]`

| Property | Value |
|---|---|
| Type | `list[dict[str, int]]` |
| Visibility | Private |
| Index 0 | Main farmer's carried items |
| Index 1+ | Hired farm hands' carried items (in hire order) |
| Initial value | `[{}]` (one empty dict for the farmer) |
| Changes | On HARVEST, PICKUP, DROP, PLACE, FEED, COLLECT_FERTILIZER; reset each end-of-day |

Items in inventory are not in the shed. They are carried in the field. At end-of-day, all inventory is dropped to the shed (overflow discarded) and inventories are cleared.

FEED consumes WHEAT from the unit's own inventory (not the shed).
FERTILIZE consumes FERTILIZER from the unit's own inventory.

---

## `market`

Shared. Both players see the same market state.

---

### `market["inventory"]`

| Property | Value |
|---|---|
| Type | `dict[str, int]` |
| Visibility | Shared |
| Keys | All 9 products: `["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]` |
| Initial value | All at `10000` (I0) |
| Changes | Every turn (town consumption at step 0 immediately moves wheat to 9999) |

Market inventory can go negative (town consumes even when inventory is 0). Negative inventory raises prices above base. Players can still buy from negative inventory (Needs experimentation — unclear if buying when inventory <= 0 is allowed or silently fails).

Selling at `$1` (floor) does NOT add to market inventory (source line ~636).

---

### `market["prices"]`

| Property | Value |
|---|---|
| Type | `dict[str, int]` |
| Visibility | Shared |
| Keys | All 9 products |
| Initial value | Base prices (WHEAT=25, CARROT=35, etc.) |
| Changes | After market processing and after town consumption each turn |

Prices are integers (rounded), floored at `$1`. The price shown reflects the end state of the **previous** turn.

---

## `town`

Shared. Both players see the same town state.

---

### `town["unlocked_shops"]`

| Property | Value |
|---|---|
| Type | `list[str]` |
| Visibility | Shared |
| Initial value | `[]` |
| Possible values | Subset of the 8 shop names |
| Changes | At end-of-day when `(day + 1) % townShopUnlockInterval == 0` |

Shop names: `BAKERY`, `PIZZA_SHOP`, `BRUNCH_SPOT`, `YARN_STORE`, `ICE_CREAM_SHOP`, `PET_CAFE`, `SMOOTHIE_SHOP`, `FARMERS_MARKET`

Shops unlock in random order. Once unlocked, a shop never locks again.

---

## Observation Visibility Summary

| Field | Public/Private | Opponent can see |
|---|---|---|
| `step` | Public | Yes |
| `day`, `hour` | Public | Yes |
| `player` | Per-agent | Each player sees their own |
| `farms[p].money` | Public | Yes |
| `farms[p].tiles` | Public | Yes (all tiles, both farms) |
| `farms[p].farmer` | Public | Yes |
| `farms[p].hands` | Public | Yes |
| `farms[p].unlocked_quadrants` | Public | Yes |
| `farms[p].hires_today` | Public | Yes |
| `private.shed` | Private | No |
| `private.seeds` | Private | No |
| `private.inventories` | Private | No |
| `market` | Public | Yes (both see same) |
| `town` | Public | Yes (both see same) |
