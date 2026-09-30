import logging
from typing import Any

from fieldops.state import ObservationParser
from fieldops.core.planner import DecisionContext
from fieldops.core.economy import EconomicModel
from fieldops.core.strategy import StrategyConfig, decide
from fieldops.managers.worker_manager import HybridWorkerManager
from fieldops.observatory.recorder import ObservatoryRecorder

logger = logging.getLogger(__name__)


class AgentCoordinator:
    """Thin coordinator: parse -> decide -> schedule -> collect actions."""

    def __init__(self):
        self.worker_manager = HybridWorkerManager()
        self.observatory = ObservatoryRecorder()
        self.last_economic_snapshot = None
        self.strategy_config = StrategyConfig()

    def __call__(self, obs: dict[str, Any]) -> dict[str, Any]:
        state = ObservationParser.parse(obs)
        snapshot = EconomicModel.calculate(state, self.last_economic_snapshot)
        self.last_economic_snapshot = snapshot

        context = DecisionContext()
        context.economic_snapshot = snapshot

        # --- Strategy decision layer (replaces the old hardcoded block) ---
        decisions = decide(state, self.strategy_config)
        self.worker_manager.preferred_crop = decisions.crop  # scheduler plants it

        # --- Worker task scheduling (existing scheduler) ---
        self.worker_manager.initialize(context)
        self.worker_manager.update(state, context)
        self.worker_manager.plan(state, context)
        scheduler_actions = self.worker_manager.execute(state, context)

        actions = {
            "farmer": scheduler_actions.get("farmer", ["PASS"]),
            "hands": scheduler_actions.get("hands")
                     or [["PASS"] for _ in range(len(state.my_farm.hands))],
            "market": decisions.market,
        }

        self.observatory.record_step(state, context, actions, snapshot)
        return actions


_coordinator_instance = AgentCoordinator()


def agent(obs: dict[str, Any], config: dict[str, Any] = None) -> dict[str, Any]:
    """FieldOps entry point."""
    if not isinstance(obs, dict):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    if obs.get("step", 0) > 718:
        try:
            _coordinator_instance.observatory.finalize()
        except Exception as e:
            logger.error(f"Observatory export failed: {e}")
        return {"farmer": ["PASS"], "hands": [], "market": []}
    return _coordinator_instance(obs)
