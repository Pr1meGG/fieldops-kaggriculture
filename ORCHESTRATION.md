# ORCHESTRATION — How FieldOps Makes Decisions

This document explains the agent's decision-making process at runtime.
It is the "how does the brain work" companion to BLUEPRINT.md's "what are the parts".

---

## The Turn Loop

Every turn, Kaggle calls `agent(obs)`. The agent must return an action dict within
the time limit. Here is the full decision sequence:

```
1. Parse observation → GameState
2. Classify the current game phase
3. Evaluate immediate obligations (watering, feeding)
4. Evaluate strategic opportunities (planting, harvesting, selling, hiring)
5. Select one farmer action
6. Select market orders
7. Format and return action dict
```

---

## Season Phases

The season has three rough phases with different optimal strategies.
These are **game phases** (early/mid/late season), not development phases from the roadmap.

### Early Game (Days 0–5)
**Goal**: Get crops in the ground and generating income ASAP.

- Buy wheat seeds (cheap, fast, reliable)
- Plant aggressively
- Water everything
- Sell harvests to accumulate capital
- Do not buy land yet (too expensive relative to early capital)

### Mid Game (Days 6–20)
**Goal**: Expand production capacity and diversify.

- Buy additional land if capital allows
- Introduce higher-value crops (melon, tomato, strawberry)
- Consider animals if capital is strong (goose is the most efficient starter)
- Hire farm hands to parallelize watering/harvesting
- Begin tracking market prices — avoid selling into a glut

### Late Game (Days 21–30)
**Goal**: Maximize final cash by harvesting everything and selling at peak prices.

- No new long-cycle crops (they won’t mature before the season ends)
- Prioritize selling inventory before day 30
- Manage market timing to avoid crashing premium prices
- Fertilize high-value crops still in their yield window

---

## Priority Ordering (Within a Turn)

When the farmer can only take one action, priorities are:

```
1. HARVEST  — if standing on a tile with harvestable yield
2. WATER    — if standing on an unwatered plant (and it needs it today)
3. FEED     — if standing on an unfed animal
4. PLANT    — if standing on an empty tile and we have seeds
5. MOVE     — navigate toward the highest-priority uncompleted task
6. PASS     — nothing productive to do
```

**Why this order?**
- Harvesting first recovers capital and frees tiles for replanting
- Watering prevents crop loss (two missed days = weed)
- Feeding prevents animal loss (two missed days = escape, unrecoverable)
- Planting before moving means we use the current tile if it is actionable
- Moving only happens when the current tile has no productive action

---

## Market Decision Logic

Market orders are evaluated separately from farmer actions.

### When to BUY seeds:
- Remaining days > crop's time-to-first-yield (it will actually produce)
- We have enough money after buying
- We have available planting tiles

### When to SELL produce:
- Shed has harvestable items
- Market price is above a minimum acceptable threshold
  (avoids selling wheat at $1 when a price bounce is likely)
- We are in late game → sell everything regardless of price

### When to HIRE a farm hand:
- We have more uncompleted watering/harvesting tasks than the farmer can complete in a day
- The cost of hiring is less than the expected additional yield value
- We have enough money

### When to BUY land:
- We have filled our current quadrant AND have excess capital
- *Hypothesis (untested)*: buy when money > $4k AND >80% of tiles are occupied
- The actual threshold will be measured and updated in `DECISIONS.md`

---

## Handling Multiple Units

When farm hands are hired:

- The planner generates a task list (water tile A, harvest tile B, etc.)
- The executor assigns one task per unit per turn
- Units closest to their assigned task are preferred
- No two units are assigned the same task

This is initially simplified: farm hands follow the same priority rule as
the farmer. Task assignment will become smarter in later iterations.

---

## What We Do NOT Do (Yet)

- Multi-turn planning (we do not simulate future game states)
- Market prediction (we react to prices, not forecast them)
- Opponent modeling (we ignore what the opponent is doing)
- Pathfinding (farmer movement is greedy, not optimal)

These are intentional deferrals. We build a solid rule-based agent first,
then instrument it to measure where we leave the most money on the table.

---

## Open Strategic Questions

These are questions we need to answer through experimentation:

1. What is the optimal crop mix for a 25-tile farm?
2. At what capital threshold is buying NE quadrant worth it?
3. Does fertilizer have positive ROI for wheat and carrot?
4. Are animals worth the upfront cost given feeding overhead?
5. What is the breakeven point for hiring a farm hand?

Answers will be documented in `DECISIONS.md` once measured.
