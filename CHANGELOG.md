# CHANGELOG — FieldOps

All meaningful changes to this project are recorded here.
Format: `## [vX.Y] — YYYY-MM-DD` followed by Added / Changed / Fixed sections.

---

## [v0.3] — 2026-08-05

### Added
- `docs/environment.md` — full environment architecture derived from source code:
  turn processing order, initialization, termination, day/hour arithmetic,
  plant decay, weed spawning, shop unlock timing, market price timing,
  PLANT validation, shed capacity, farmer/hand reset, town consumption, reward
- `docs/observation_schema.md` — every observation field with type, visibility,
  possible values, and when it changes (verified against live experiments)
- `docs/action_schema.md` — every farmer, hand, and market action with parameters,
  requirements, failure conditions, and expected results

### Key discoveries from source reading
- `step` IS in the observation (injected by framework, not interpreter)
- Shed always contains zero-valued keys for all products/animals at init
- Empty structure tile has NO `"animal"` key (check `"animal" in tile`)
- DONE fires at step >= episodeSteps - 2 (agent never sees final step)
- PLANT validation is binary: if any unit over-requests, ALL PLANTs for that crop become PASS
- Selling at $1 does NOT add to market inventory
- Town center consumes starting at step 0 (market prices shift immediately)
- CROPS source values differ from competition/README.md for Tomato/Melon max_yield_day

---

## [v0.2] — 2026-08-05

### Changed
- `ROADMAP.md` — reduced from 10 phases to 6; merged trivial phases (land expansion
  into multi-unit coordination, late-game selling into market awareness);
  removed phase numbering from game-season concepts to avoid collision with
  development phase numbering; marked Phase 0 as complete
- `BLUEPRINT.md` — removed premature future module names (`market_model.py`,
  `pathfinder.py`, `scheduler.py`, `evaluator.py`); replaced with a principle:
  create modules when a concrete need arises, not speculatively
- `ORCHESTRATION.md` — renamed "Phase 1/2/3" game sections to "Early/Mid/Late Game"
  to prevent collision with roadmap phase numbering; labeled the $4k/$80% land-buy
  rule as an untested hypothesis rather than stated guidance
- `DECISIONS.md` — removed ADR that duplicated BLUEPRINT content; added ADR-003
  documenting the decision not to create speculative modules; improved ADR framing
  to only record decisions not obvious from the code
- `TASKS.md` — updated to reflect Phase 1 sprint (Phase 0 was already complete);
  removed redundant Backlog section (ROADMAP.md is the single source of truth)
- `README.md` — improved "Development Workflow" section to give actual guidance
  instead of three bare links

---

## [v0.1] — 2026-08-05

### Added
- Project initialized:
  - Documentation foundation: `README.md`, `BLUEPRINT.md`, `ORCHESTRATION.md`,
    `ROADMAP.md`, `TASKS.md`, `CHANGELOG.md`, `DECISIONS.md`
  - `src/fieldops/` package skeleton: `constants.py`, `agent.py`, `state.py`,
    `planner.py`, `executor.py`
  - Competition docs in `competition/`
  - Basic smoke test at `tests/test.py`
