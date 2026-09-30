# DECISIONS — Architectural Decision Records

This file records significant decisions that are **not obvious from reading the code**.
The test: if someone asks "why did you do it this way?", the answer lives here.

Format per entry:
- **Date** — when the decision was made
- **Status** — Accepted / Superseded / Rejected
- **Context** — what problem triggered this decision
- **Decision** — what we chose
- **Alternatives considered** — and why we rejected them
- **Consequences** — tradeoffs, follow-up actions, open questions

---

## ADR-001 — Typed dataclasses for observation parsing

**Date**: 2026-08-05
**Status**: Accepted

**Context**:
The raw observation is a nested dict where tile values can be `None`, `"LOCKED"`,
or one of several different dicts — all mixed in the same 2D array. Working with
this directly means sprinkling `isinstance()` and `is None` checks throughout
every module that touches tiles. That is fragile and hard to test.

**Decision**:
`state.py` owns all raw-dict access. It converts the observation into typed
dataclasses once per turn. Everything else works with those objects.

**Alternatives considered**:
- Raw dicts everywhere — simpler to start, but every module becomes a defensive-check
  maze. Bugs from missing checks are silent and hard to trace.
- Pydantic validation — adds an external dependency and runtime overhead for a
  problem that dataclasses already solve adequately.

**Consequences**:
- `state.py` must stay in sync with the observation schema (low risk — competition
  rules are stable during a season)
- All other modules become significantly easier to read and unit-test

---

## ADR-002 — Rule-based agent before any ML

**Date**: 2026-08-05
**Status**: Accepted

**Context**:
Reinforcement learning is the obvious end-state for a game-playing agent. However,
starting with RL has known failure modes: unstable training, reward shaping bugs,
long feedback loops, and no interpretable baseline to debug against.

**Decision**:
Build a complete rule-based agent first. Do not add ML until:
1. The rule-based agent has a measurable performance ceiling, AND
2. We have identified specific decisions where ML would outperform rules, AND
3. We have enough episode data to train on meaningfully.

**Alternatives considered**:
- RL from day one — high risk of getting stuck before having a working agent at all.
- LLM-based planning — almost certainly too slow per turn; evaluation is opaque.

**Consequences**:
- We have a competitive, debuggable agent sooner
- Every decision is inspectable: we can print exactly why the agent did what it did
- ML can be layered in later without rewriting the architecture

---

## ADR-003 — No speculative module creation

**Date**: 2026-08-05
**Status**: Accepted

**Context**:
During initial planning, it was tempting to pre-name future modules
(`market_model.py`, `pathfinder.py`, `scheduler.py`, `evaluator.py`).
Naming a module before it exists creates an implicit commitment and anchors
future thinking to a structure that may not fit the actual need.

**Decision**:
No module is created until there is a concrete, immediate need for it.
When a concern outgrows its current home, extract it then — with a real use case
to validate the design.

**Alternatives considered**:
- Plan full module structure upfront — feels organized, but locks in decisions
  before we understand what the code actually needs.

**Consequences**:
- The module list may grow organically and look different from what was initially imagined
- That is acceptable — real structure is better than planned structure

---

## ADR-004 — All numeric game constants in constants.py

**Date**: 2026-08-05
**Status**: Accepted

**Context**:
The competition rules contain many numeric values that appear in multiple places
(24 turns/day, 30 days, $3000 starting money, crop yield windows, etc.).

**Decision**:
Every game constant is defined by name in `constants.py`. No raw integers appear
in strategy or execution logic.

**Alternatives considered**:
- Pull from `obs["configuration"]` at runtime — more dynamic, but adds complexity
  and the defaults do not change within a competition.
- Scatter constants near their point of use — common pattern, but creates a
  maintenance burden when values need updating.

**Consequences**:
- `constants.py` must be kept in sync with the competition rules
- Strategy code is significantly more readable (`TURNS_PER_DAY` vs `24`)

---

*New decisions will be added as they are made. Only decisions that are not obvious from the code or BLUEPRINT.md belong here.*

## Experiment Log — V1 → V2 (PROMOTED, locked 2026-09-30)
- Change: target_crops 12 → 20 (src/fieldops/core/strategy.py, default StrategyConfig.target_crops)
- Benchmark: simulate_20.py, seeds 1–20, one clean invocation
- V1 mean: $37,103.10 → V2 mean: $49,212.55 (delta +$12,109.45 / +32.63%)
- V2 stats: median $49,057 | min $48,234 | max $50,001 | stdev $403.91
- Illegal actions: 0 | Runs completed: 20/20 | Melons harvested: 765 (V1: 438)
- V2 is now the locked control. No further runs at target_crops=24 without approval.

## EXP-001 (2026-09-30): target_crops 20 → 24 on V3 — REJECT (25 seeds-equivalent 20-seed protocol)
mean 48,532.45 vs control 50,106.20. Delta -1,573.75. Restored control.

## EXP-002: task_mult 1.6 → 1.3 / 1.5 — REJECT (ties 1.5, loses at 1.3)
## EXP-003: max_hires 3 → 4 — REJECT (49,769.20)
## EXP-004: cash_reserve 250 → 150 — REJECT (identical, non-binding)
## EXP-005: double-hire day 0 — REJECT (49,969.25)
## EXP-006: BUY_LAND expansion — REJECT (43,359.00)

## SUBMISSION VALIDATION V3 (50 seeds): mean $50,083.56, std $95, min 49,630, max 50,360

## V5 cycle (2026-09-30)
- EXP-007 harvest-before-water: +$97.8 → PROMOTE (V4: 50,204.15)
- EXP-008 task_mult 1.4: +$240.8 → PROMOTE (V5: 50,444.95)
- EXP-009 task_mult 1.2: -192.7 → REJECT
- EXP-010 TC=22 on V5: -591.9 → REJECT; TC=21: -1,039; TC=18: -1,492 → TC=20 confirmed peak
- EXP-011 max_hires=5 on V5: -1,189 → REJECT
- Sell-floor $200: -605.9 → REJECT (on V3)
- BUY_LAND: -6,747 → REJECT; fertilizer buy: untested worker path, dropped as low-ROI

## CHAMPION: V5 (d7dbca5) — TC=20, max_hires=3, task_mult=1.4, harvest-first priority. 20-seed mean $50,444.95
