"""
planner.py — Strategy layer.

WHY THIS FILE EXISTS:
    The planner answers the question: "What should we do this turn?"

    It receives a typed GameState and produces a Plan — a structured
    description of intent. The Plan does NOT contain action strings.
    That is the executor's job.

    Keeping strategy separate from output formatting means:
    - Strategy can be tested without worrying about action syntax
    - Formatting can change without touching strategy logic
    - Each module has exactly one reason to change

STATUS: stub — Plan dataclass is defined but plan() is not yet implemented.
    This will be fully implemented in Phase 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .state import GameState


# ---------------------------------------------------------------------------
# Plan — the output of the planner
# ---------------------------------------------------------------------------

@dataclass
class FarmerIntent:
    """
    What we want the main farmer to do this turn.

    The executor will convert this into a concrete action string.
    """
    action: str               # e.g. "WATER", "HARVEST", "MOVE", "PLANT", "PASS"
    target: tuple[int, int] | None = None   # tile to act on, or move destination
    crop: str | None = None   # for PLANT actions


@dataclass
class Plan:
    """
    The planner's output for a single turn.

    Contains what we want each unit to do and what market orders to submit.
    The executor translates this into the final action dict.
    """
    farmer_intent: FarmerIntent
    hand_intents: list[FarmerIntent] = field(default_factory=list)
    market_orders: list[list[Any]] = field(default_factory=list)
    # e.g. [["BUY_SEED", "WHEAT", 3], ["SELL", "WHEAT", 5]]


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

def plan(state: GameState) -> Plan:
    """
    Decide what the agent should do this turn.

    Args:
        state: The current typed game state.

    Returns:
        A Plan describing the intended actions for this turn.

    This function is the strategic heart of the agent. It will grow
    significantly as phases are implemented. Keep it readable by
    delegating to private helper functions.
    """
    # TODO: implement in Phase 1
    raise NotImplementedError(
        "planner.plan() is not yet implemented. "
        "This will be built in Phase 1."
    )
