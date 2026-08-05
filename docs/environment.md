# Environment Architecture

**Source**: `kaggle_environments/envs/kaggriculture/kaggriculture.py`  
**Config**: `kaggle_environments/envs/kaggriculture/kaggriculture.json`  
**Version**: 0.1.0

This document describes the Kaggriculture environment's internal architecture: how it initialises, how each turn is processed, and how the episode ends. It is derived directly from reading the source code and live experiments, not from the public documentation.

---

## Environment Architecture Overview

Kaggriculture is a **two-player** environment managed by the `kaggle-environments` framework. The game state is stored in **shared observation objects** — not in a central game object. The `interpreter()` function is called every turn and mutates state in place.

```
Kaggle framework
    |
    |-- calls interpreter(state, env) every turn
    |       state[0].observation  <-- shared game state (farms, market, town)
    |       state[1].observation  <-- same objects, different private field
    |
    |-- calls agent(obs) for each player
    |       obs is derived from state[i].observation
    |
    +-- records state at each step for replay
```

### Key Architectural Facts

1. **State is mutable dicts, not objects.** Tiles, farms, market — all are plain Python dicts mutated in place. There are no classes.
2. **Shared state via reference.** `state[0].observation.farms` and `state[1].observation.farms` point to the **same list**. Both players see the same farm tiles. Mutations are immediately visible to both.
3. **Private state is separate.** `state[i].observation.private` is unique per player and is never shared.
4. **The interpreter is the game loop.** There is no separate game class. The single `interpreter()` function handles all game logic.
5. **`step` in the observation** is injected by the Kaggle framework, not by the interpreter. It is 0-indexed and IS present in the observation dict.

---

## Initialization

Called once when `obs0.farms` is absent or empty.

```
_initialize(state, env)
```

What it sets up:
- One `farm` dict per player (10x10 tiles, NW quadrant unlocked, farmer at (4,4), money=3000)
- One `private` dict per player (shed, seeds, inventories all zeroed)
- One shared `market` dict (all products at I0=10,000 inventory and base price)
- One shared `town` dict (no unlocked shops)
- A random seed resolved via `resolve_episode_seed(env)` (stored in `env.info["seed"]`)

The farmer's starting position is **(4, 4)** — the NW shed-access tile. This is the only NW-quadrant tile that is also shed-adjacent.

---

## Turn Processing Order

Every call to `interpreter()` executes in this exact sequence:

```
1.  Player actions (farmer + hands, simultaneously for both players)
    -- Atomic PLANT validation first:
       if total PLANT requests for a crop > available seeds
       -> all PLANTs for that crop become PASS (none plant)
    -- _apply_unit_action() for each unit of each player

2.  Market processing
    -- _process_market():
       HIRE and BUY_LAND processed first (atomic, in player order)
       then SELL / BUY_* in per-unit lockstep:
         quote both players -> commit both -> repeat until done

3.  Town consumption
    -- _town_consume():
       shops drain market inventory every townShopSellInterval turns
       town center drains market every townCenterSellInterval turns
       prices refreshed after town drains

4.  Plant decay
    -- _decay_plants():
       any plant past max_lifespan_step loses 1 yield_units every 2 steps
       if yield_units reaches 0 -> tile becomes WEED

5.  End-of-day (only when (step+1) % turnsPerDay == 0)
    -- _daily_refresh_plants(): resets watered_today, increments consecutive_unwatered,
       converts un-watered plants to weeds, fires ongoing crop yields
    -- _daily_refresh_animals(): resets fed_today, increments consecutive_unfed,
       removes escaped animals (structure remains), fires animal yields and care bonus
    -- _spawn_weeds(): random weed spawn on empty unlocked tiles
    -- _drop_inventories_to_shed(): all farmer/hand inventories dropped to shed (overflow discarded)
    -- Farmer reset to (4,4); all hands removed; hires_today reset to 0
    -- Shop unlock: if (day+1) % townShopUnlockInterval == 0, random shop added

6.  Observation update
    -- day and hour updated for next turn
    -- shared fields (farms, market, town, day, hour) propagated to state[1]

7.  Termination check
    -- if step >= episodeSteps - 2:
       all agents set to DONE
       reward = farms[player]["money"]
```

**Critical**: The agent sees the observation from the **start** of the turn, before the turn is processed. The `step` field in the observation is the step index for which the agent is being asked to act.

---

## Episode Termination

Source code (line ~937):
```python
if step >= cfg.episodeSteps - 2:
    for s in state:
        s.status = "DONE"
        s.reward = float(obs0.farms[s.observation.player]["money"])
```

- With `episodeSteps=720`, DONE fires when `step >= 718`.
- The agent sees steps 0 through 718 (total of 719 calls). **It does not see step 719.**
- `env.steps` has `episodeSteps` entries (0 through 719), where index 719 has status `DONE`.
- Reward = **final money in the bank only**. Unsold shed inventory does NOT count.

Verified by experiment: with `episodeSteps=6`, agent called at steps [0,1,2,3,4], status DONE at env.steps index 5.

---

## Day/Hour Arithmetic

```python
day  = step // turnsPerDay    # 0-indexed
hour = step  % turnsPerDay    # 0-indexed, 0..23
```

- Day 0, Hour 0 = step 0 (the very first turn).
- End-of-day processing fires at the last turn of a day: `(step + 1) % turnsPerDay == 0`.
- At turnsPerDay=24: end-of-day fires at steps 23, 47, 71, ... (every 24 turns).
- The observation `day` and `hour` shown to the agent reflect the **start of the turn**, not post-processing.

---

## Weed Spawning

- Happens once per day, during end-of-day processing.
- RNG seeded deterministically: `random.Random((seed * 1_000_003) ^ day)`.
- Same RNG used for shop unlock choice on that day.
- Affects only empty (`None`) unlocked tiles. Does NOT affect `"LOCKED"` tiles.
- Chance: 0.005 per empty tile per day.

---

## Shop Unlock Timing

A new shop unlocks if `(day + 1) % townShopUnlockInterval == 0` during end-of-day. With interval=3:

| After day | Shop unlock # |
|---|---|
| Day 2 | 1st |
| Day 5 | 2nd |
| Day 8 | 3rd |
| Day 11 | 4th |
| Day 14 | 5th |
| Day 17 | 6th |
| Day 20 | 7th |
| Day 23 | 8th (max, 8 total shops) |

Order is random. All 8 shops can potentially unlock by day 23 of 29.

---

## Market Price Update Timing

Prices are refreshed in two places per turn:
1. **After market processing** — `_process_market` calls `_refresh_prices` once at end
2. **After town consumption** — `_town_consume` calls `_refresh_prices`

**The observation `market.prices` shows prices from the END of the previous turn.** During selling, the actual price received is based on the current (live) inventory at each unit commitment, not the observed price.

Confirmed by experiment: on step 0 (both players PASS), wheat inventory drops from 10,000 to 9,999 (town center consumes at step 0), and price rises from 25 to 26.

---

## Plant Decay Mechanics

`_decay_plants()` runs every turn (not just end-of-day).

```python
mls = tile["max_lifespan_step"]
if mls < 0 or step < mls:
    continue
if (step - mls) % 2 != 0:   # fires every OTHER step
    continue
tile["yield_units"] -= 1
if tile["yield_units"] <= 0:
    tile = {"kind": "WEED"}
```

- **One-time crops**: `max_lifespan_step = (planted_day + max_yield_day + 1) * turns_per_day`
  - Wheat planted day 0: max_lifespan_step = (0 + 4 + 1) * 24 = 120
- **Ongoing crops**: `max_lifespan_step = -1` at creation; set to `(next_day + 1) * turns_per_day` when final scheduled yield fires.
- Decay removes 1 yield_unit every **2 steps**. A plant with yield_units=6 at decay start takes 12 turns to become a weed.

---

## Atomic PLANT Validation

Before applying any unit action this turn, the interpreter counts all PLANT requests:

```python
plant_demand = {}   # {crop: count_of_PLANT_requests_this_turn}
blocked = {crop for crop, n in plant_demand.items() if n > seeds.get(crop, 0)}
# All PLANT actions for blocked crops become PASS
```

If 2 units both try to PLANT WHEAT but only 1 seed is available, **both are converted to PASS**. Zero seeds planted. This is binary — not first-come-first-served.

**Multi-unit rule**: never assign more PLANT actions for a crop in one turn than you have seeds for that crop.

---

## Shed Capacity Enforcement

`shedCapacity = 100` applies to ALL non-seed items combined. Check points:
- `BUY_PRODUCT` market order: fails silently if shed full
- `BUY_ANIMAL` market order: fails silently if shed full
- `DROP` farmer action: fills to capacity, overflow discarded
- `PLACE` farmer action (shed-drop variant): fills to capacity
- End-of-day inventory drop: items that don't fit are discarded permanently

Seeds are NEVER in the shed. They live in `private["seeds"]` with no capacity limit.

---

## Farmer/Hand Spawn and Reset

At end-of-day:
- Farmer resets to **(4, 4)**.
- All hands are **removed** — `farm["hands"] = []`.
- All farmer/hand inventories dropped to shed, then cleared.
- `hires_today` resets to 0.

Each hired hand appears at the shed-adjacent tile with the fewest current occupants (NWSE tie-breaking). First hand of each day goes to **(5, 4)** — which is in the NE quadrant and is LOCKED until that quadrant is purchased. A hand spawned on a locked tile can act normally (move off it), but cannot perform tile actions while standing on it.

---

## Town Consumption Details

**Town center** (every `townCenterSellInterval` turns, default 12):

| Day range | Units consumed per product per tick |
|---|---|
| Days 0-9 | 1 |
| Days 10-19 | 2 |
| Days 20-29 | 4 |

Products consumed by town center: all except FERTILIZER.

**Each unlocked shop** (every `townShopSellInterval` turns, default 4):
- Single-product shops (YARN_STORE, PET_CAFE): **2 units** per tick
- Multi-product shops: **1 unit** per product per tick

Town consumption does NOT pay players. It only drains market inventory, which raises prices.

---

## Reward Calculation

```python
reward = float(farm["money"])
```

- Applied when `status == "DONE"`
- Floating point (money accumulates as float)
- Unsold inventory: **zero value**
- Unharvested crops: **zero value**
- Both players receive their own money as their individual reward
- Win condition: higher reward wins. Tie is possible.

---

## Built-in Agents

Three agents are available by name string:

| Name | Description |
|---|---|
| `"pass"` | Returns PASS every turn. Useful as a stationary dummy. |
| `"random"` | Random movement + occasional seed buy + random PLANT. Very weak. |
| `"starter"` | Carrot loop on a single tile: buy seed, plant, water, harvest at max_yield_day, sell. |

The starter agent is the baseline to beat in Phase 1. It only works one tile and ignores most game mechanics.
