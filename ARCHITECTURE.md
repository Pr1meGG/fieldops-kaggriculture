# FieldOps Architecture

This document describes the Phase 0 (Foundation) architecture of the Kaggriculture agent.

## Core Philosophy
The core philosophy of this rebuild is strict separation of concerns. `agent.py` no longer contains any business logic; it functions solely as a coordinator. 

Data flows linearly:
`Raw Observation -> GameState -> DecisionContext -> Managers -> Actions`.

## Shared State
- **GameState**: An immutable, structured representation of the Kaggle environment observation. Managers read this to understand the environment, but never mutate it.
- **DecisionContext**: A lightweight shared object passed sequentially to all managers. Used for inter-manager communication (e.g., worker reservations, tile reservations, planned investments).

## Manager Interfaces
Every manager implements `BaseManager` which dictates four lifecycle methods per step:
1. `initialize(context)`
2. `update(state, context)`
3. `plan(state, context)`
4. `execute(state, context) -> dict`

## Architecture Ownership Map
The components of this architecture map directly to the locked project phases. No manager should implement logic belonging to a future phase.

- **EconomyManager** -> Phase 1
- **ExpansionManager** -> Phase 2
- **WorkerManager** -> Phase 3 & 4
- **CropManager** -> Phase 5
- **LivestockManager** -> Phase 6
- **MarketManager** -> Phase 7
- **Planner / Core** -> Phase 8-10

## Current Status
- **Phase Status**: Phase 0 Complete
- **Current Branch**: fieldops-v2
- **Current Champion**: V0 (Foundation Stub)
- **Next Phase**: Phase 1 (Economy Engine)
