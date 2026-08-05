# BLUEPRINT — FieldOps Architecture

This document describes the high-level architecture of the FieldOps agent.
Read this before writing any new module or making structural changes.

---

## Design Principles

1. **Never modify many unrelated files in one task.**
   Changes should be scoped to a clear, named feature or fix.

2. **Every feature should be modular.**
   A strategy module should be swappable without touching the agent entry point.

3. **Every important class should have one responsibility.**
   `state.py` parses. `planner.py` plans. `executor.py` outputs. They do not cross.

4. **Avoid magic numbers.**
   All game constants live in `constants.py`. No raw integers scattered in logic.

5. **Prefer composition over giant files.**
   A module that exceeds ~200 lines should be reviewed for splitting.

6. **Every optimization should have a measurable reason.**
   Benchmark before and after. Document the result in `CHANGELOG.md`.

7. **Keep functions short.**
   A function that does not fit on one screen is probably doing too much.

8. **Document complex logic.**
   If the "why" is not obvious, write a docstring or inline comment.

9. **Prefer deterministic code before AI-based heuristics.**
   Rule-based logic first. ML layer only if it demonstrably improves results.

10. **Never overengineer.**
    Do not add abstraction until you have two concrete uses for it.

---

## Module Map

```
src/fieldops/
├── agent.py        Entry point. Receives obs, returns action dict.
├── state.py        Parses raw observation into typed Python objects.
├── planner.py      Decides WHAT to do this turn (strategy layer).
├── executor.py     Decides HOW to express that plan as a valid action dict.
└── constants.py    All game constants referenced by name, not by value.
```

### `agent.py` — Entry Point

**Responsibility**: Provide the `agent(obs)` function that Kaggle calls.

- Receives raw `obs` dict from the environment
- Calls `state.parse(obs)` → typed `GameState`
- Calls `planner.plan(state)` → a `Plan` object
- Calls `executor.execute(plan, state)` → a valid action dict
- Returns that dict

This module should be **thin**. No logic lives here.

---

### `state.py` — Observation Parser

**Responsibility**: Convert raw dicts into structured, typed Python objects.

Why this matters: the raw observation is a nested dict of mixed types.
Working with it directly throughout the codebase is fragile and verbose.
A typed `GameState` object makes the rest of the code readable and safe.

Key objects to produce:
- `GameState` — top-level snapshot of the game
- `FarmState` — one player's farm (tiles, money, positions)
- `Tile` — a typed union: `EmptyTile | LockedTile | PlantTile | WeedTile | AnimalTile`
- `MarketState` — prices and inventories
- `PrivateState` — shed, seeds, inventories

---

### `planner.py` — Strategy Layer

**Responsibility**: Decide what the agent should do this turn.

This is the brain of the agent. It answers questions like:
- What crops should I plant right now?
- Which tiles need watering?
- Should I sell now or wait for prices to recover?
- Do I have enough money to buy more land?
- Should I hire a farm hand today?

The planner produces a `Plan` — a structured description of intent,
**not** an action string. The executor converts intent into valid game actions.

Why separate planner from executor?
→ Strategy and action formatting have different reasons to change.
→ You can test strategy logic without worrying about action string syntax.

---

### `executor.py` — Action Formatter

**Responsibility**: Convert a `Plan` into a valid action dict.

- Accepts a `Plan` and the current `GameState`
- Resolves movement paths for the farmer
- Formats all actions into the `{"farmer": [...], "hands": [...], "market": [...]}` schema
- Handles the constraint: farmer takes one action per turn

---

### `constants.py` — Game Constants

**Responsibility**: Name every game constant so no raw values appear in logic.

Examples:
```python
TURNS_PER_DAY = 24
TOTAL_DAYS = 30
TOTAL_TURNS = 720
STARTING_MONEY = 3000
SHED_CAPACITY = 100
BOARD_SIZE = 10
```

Also includes crop metadata, animal metadata, and price curve parameters.

---

## Data Flow

```
Kaggle env
    │
    ▼  raw obs dict
agent.py
    │
    ▼  parse()
state.py  →  GameState
    │
    ▼  plan()
planner.py  →  Plan
    │
    ▼  execute()
executor.py  →  action dict
    │
    ▼
Kaggle env
```

---

## Adding New Modules

When a new concern outgrows its current home (e.g. market logic in the planner
grows large enough to deserve its own file), extract it into a new module that
plug into the planner — not into `agent.py`.

Do not create new modules speculatively. Create them when a concrete need arises.

---

## Testing Philosophy

- Unit tests cover individual functions in isolation
- Integration tests run a short episode and check that the agent does not crash
- Performance tests benchmark reward against the `random` and `starter` agents
- All tests live in `tests/`

---

## Key Constraints (from the competition)

- Agent function is called **every turn** (720 turns per game)
- Agent must return within the time limit (keep logic fast)
- No state is persisted between calls — state must be reconstructed from `obs`
- The `private` field in `obs` is only for your own player
- The action dict must have the exact schema Kaggle expects (executor's job)
