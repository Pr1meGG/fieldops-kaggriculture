"""
agent.py — FieldOps entry point.

This is the only file that Kaggle calls. It is intentionally thin:
all logic lives in state.py, planner.py, and executor.py.

The agent() function signature must match what Kaggle expects:
    def agent(obs: dict) -> dict

The returned dict must have the shape:
    {
        "farmer": [op, ...args],
        "hands":  [[op, ...args], ...],
        "market": [[op, ...args], ...],
    }
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def agent(obs: dict[str, Any]) -> dict[str, Any]:
    """
    FieldOps agent entry point.

    Receives the raw observation from the Kaggriculture environment and
    returns a valid action dict.

    Args:
        obs: Raw observation dict from the environment. See competition/AGENTS.md
             for the full schema.

    Returns:
        Action dict with keys "farmer", "hands", and "market".
    """
    # Phase 0: stub — returns PASS on every turn.
    # This will be replaced in Phase 1 when state.py and planner.py are built.
    return {
        "farmer": ["PASS"],
        "hands": [],
        "market": [],
    }
