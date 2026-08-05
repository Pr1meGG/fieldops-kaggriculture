# TASKS — Active Task List

This file tracks the current sprint. It is updated as tasks are started, completed, or blocked.

Status markers:
- `[ ]` Not started
- `[/]` In progress
- `[x]` Complete
- `[!]` Blocked (reason noted inline)

---

## Current Sprint: Phase 1 — Baseline Agent

- [ ] Implement `state.py` — observation parser with typed dataclasses
- [ ] Implement `planner.py` — wheat-loop strategy (plant → water → harvest)
- [ ] Implement `executor.py` — action formatter and greedy movement
- [ ] Write unit tests for `state.parse()`
- [ ] Write integration test: run a full episode, agent does not crash
- [ ] Benchmark: win rate vs `random` over 10 episodes

---

## Completed

- [x] Phase 0: All documentation and package skeleton created; `tests/test.py` passes

---

## Notes

- Every task should result in a commit suggestion when it is complete
- The backlog lives in `ROADMAP.md` — this file only tracks the active sprint
