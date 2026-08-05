# ROADMAP — FieldOps Development Phases

This document tracks the planned development phases for the FieldOps agent.
Each phase has a clear goal and a definition of done.

Status markers:
- `[ ]` Not started
- `[/]` In progress
- `[x]` Complete

---

## Phase 0 — Project Foundation
**Goal**: Establish a clean, well-documented project structure before writing any agent logic.

- [x] Write `README.md`, `BLUEPRINT.md`, `ORCHESTRATION.md`, `ROADMAP.md`, `TASKS.md`, `CHANGELOG.md`, `DECISIONS.md`
- [x] Create `src/fieldops/` package skeleton (`constants.py`, `agent.py`, `state.py`, `planner.py`, `executor.py`)
- [x] Verify `tests/test.py` passes (environment loads cleanly)

**Done when**: All docs exist. Package skeleton is importable. Tests pass. ✅

---

## Phase 1 — Baseline Agent
**Goal**: Build a working agent that beats the `random` opponent consistently.

- [ ] Implement `state.py` — parse raw observation into typed `GameState`
- [ ] Implement wheat-loop strategy in `planner.py` and `executor.py`: plant → water → harvest → sell → repeat
- [ ] Write unit tests for state parsing
- [ ] Write integration test: run a full episode without crashing
- [ ] Benchmark: win rate vs `random` over 10 episodes

**Done when**: Agent wins >70% against `random`. All tests pass.

---

## Phase 2 — Multi-Crop Strategy
**Goal**: Intelligent crop selection based on days remaining and market prices.

- [ ] Crop selection logic: evaluate expected revenue given days remaining
- [ ] Only plant crops that will mature before the season ends
- [ ] Add fertilizer usage for high-value crops in the yield window
- [ ] Write unit tests for crop selection decisions
- [ ] Benchmark: win rate and average final cash vs Phase 1

**Done when**: Agent beats `starter` >50% of the time.

---

## Phase 3 — Market Awareness
**Goal**: React to market prices rather than selling blindly.

- [ ] Avoid selling into a glut (price below a configurable threshold)
- [ ] Sell premium goods (melon, strawberry, milk, wool) in small batches to avoid crashing the price
- [ ] Late-season mode: sell everything regardless of price once it is too late to reinvest
- [ ] Write unit tests for sell-timing decisions
- [ ] Benchmark: average revenue improvement vs Phase 2

**Done when**: Average revenue per game measurably increases vs Phase 2.

---

## Phase 4 — Multi-Unit Coordination and Land Expansion
**Goal**: Use farm hands and additional land profitably.

- [ ] Hire decision logic: estimate value of additional parallel watering/harvesting actions
- [ ] Task assignment: no two units assigned the same tile
- [ ] Land-buy decision: buy next quadrant when tiles are saturated and capital allows
- [ ] Write tests for task assignment and hire decision
- [ ] Benchmark: improvement vs Phase 3

**Done when**: Agent hires and expands when profitable, not never or always.

---

## Phase 5 — Animals
**Goal**: Integrate livestock when it is worth the upfront cost.

- [ ] Goose first (cheapest, eggs have stable demand and daily yield)
- [ ] Animal care loop: build coop/pasture → place → feed daily → harvest
- [ ] Feed-cost tracking: wheat consumed vs product earned
- [ ] Write tests for animal care logic
- [ ] Benchmark: animal ROI vs crop-only strategy

**Done when**: Agent uses animals profitably when capital allows.

---

## Phase 6 — Measurement and Tuning
**Goal**: Replace guessed thresholds with measured ones.

- [ ] Build offline episode runner to benchmark strategies quickly
- [ ] Run 50+ episode benchmarks for key decision thresholds (crop mix, hire cost, land-buy timing)
- [ ] Document results in `DECISIONS.md`
- [ ] Tune thresholds based on data, not intuition

**Done when**: Every major threshold has a measured justification in `DECISIONS.md`.

---

## Notes

- Phases are roughly sequential but can overlap
- Each phase ends with a benchmark — no phase is "done" without measuring the result
- New phases can be added as the project evolves; keep them small and purposeful
- Pathfinding, opponent modeling, and ML are not planned — they will be added only if measurement shows a clear gap that rule-based logic cannot close
