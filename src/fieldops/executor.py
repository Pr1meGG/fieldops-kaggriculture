"""
executor.py — Action formatter.

WHY THIS FILE EXISTS:
    The executor answers the question: "How do we express our plan as a
    valid Kaggriculture action dict?"

    It receives a Plan from the planner and a GameState, and produces
    the exact dict format that Kaggle expects:

        {
            "farmer": [op, ...args],
            "hands":  [[op, ...args], ...],
            "market": [[op, ...args], ...],
        }

    Responsibilities:
    - Convert FarmerIntent to an action list (e.g. ["WATER"] or ["PLANT", "WHEAT"])
    - Resolve single-step movement toward a target tile
    - Format market orders correctly

    The executor does NOT make strategic decisions. If a Plan says
    "move to (3, 2)", the executor picks the right direction — it does
    not question whether (3, 2) was the right choice.

STATUS: stub — execute() is not yet implemented.
    This will be fully implemented in Phase 1.
"""

from __future__ import annotations

from typing import Any

from .state import GameState
from .planner import Plan, FarmerIntent
from .constants import (
    ACTION_NORTH, ACTION_SOUTH, ACTION_EAST, ACTION_WEST, ACTION_PASS
)


def execute(plan: Plan, state: GameState) -> dict[str, Any]:
    """
    Convert a Plan into a valid Kaggriculture action dict.

    Args:
        plan:  The planner's output for this turn.
        state: The current game state (needed for position resolution).

    Returns:
        A dict with keys "farmer", "hands", and "market".
    """
    # TODO: implement in Phase 1
    raise NotImplementedError(
        "executor.execute() is not yet implemented. "
        "This will be built in Phase 1."
    )


def _resolve_farmer_action(intent: FarmerIntent, state: GameState) -> list[Any]:
    """
    Convert a FarmerIntent into a concrete action list.

    For MOVE intents, picks the direction that gets the farmer one step
    closer to the target (greedy movement, not optimal pathfinding).

    Args:
        intent: The intended action.
        state:  Current game state (for position lookup).

    Returns:
        An action list, e.g. ["WATER"], ["NORTH"], ["PLANT", "WHEAT"].
    """
    # TODO: implement in Phase 1
    raise NotImplementedError("_resolve_farmer_action() is not yet implemented.")


def _step_toward(
    current: tuple[int, int], target: tuple[int, int]
) -> str:
    """
    Return the cardinal direction that makes one step of progress toward target.

    Prefers horizontal movement when both axes need progress.
    This is greedy movement — not optimal, but sufficient for Phase 1.

    Args:
        current: (x, y) position of the unit.
        target:  (x, y) destination tile.

    Returns:
        One of "NORTH", "SOUTH", "EAST", "WEST".
    """
    cx, cy = current
    tx, ty = target

    dx = tx - cx
    dy = ty - cy

    # Prefer horizontal movement first to avoid edge cases at corners.
    if dx > 0:
        return ACTION_EAST
    if dx < 0:
        return ACTION_WEST
    if dy > 0:
        return ACTION_SOUTH
    if dy < 0:
        return ACTION_NORTH

    # Already at target — caller should not be issuing a MOVE intent.
    return ACTION_PASS
