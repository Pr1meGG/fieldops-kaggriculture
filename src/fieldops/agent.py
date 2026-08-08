import logging
from typing import Any

from fieldops.state import ObservationParser
from fieldops.core.planner import DecisionContext
from fieldops.managers.economy_manager import EconomyManager
from fieldops.managers.expansion_manager import ExpansionManager
from fieldops.managers.worker_manager import WorkerManager
from fieldops.managers.crop_manager import CropManager
from fieldops.managers.livestock_manager import LivestockManager
from fieldops.managers.market_manager import MarketManager

logger = logging.getLogger(__name__)

class AgentCoordinator:
    def __init__(self):
        # Initialize Managers
        self.managers = [
            EconomyManager(),
            ExpansionManager(),
            WorkerManager(),
            CropManager(),
            LivestockManager(),
            MarketManager()
        ]

    def __call__(self, obs: dict[str, Any]) -> dict[str, Any]:
        # 1. Read Observation & Build GameState
        state = ObservationParser.parse(obs)
        
        # 2. Create DecisionContext
        context = DecisionContext()
        
        # 3. Call Managers (Initialize, Update, Plan)
        for manager in self.managers:
            manager.initialize(context)
            
        for manager in self.managers:
            manager.update(state, context)
            
        for manager in self.managers:
            manager.plan(state, context)
            
        # 4. Collect Actions
        actions = {
            "farmer": ["PASS"],
            "hands": [["PASS"] for _ in range(len(state.my_farm.hands))],
            "market": []
        }
        
        for manager in self.managers:
            mgr_actions = manager.execute(state, context)
            if "farmer" in mgr_actions and mgr_actions["farmer"]:
                actions["farmer"] = mgr_actions["farmer"]
            
            if "hands" in mgr_actions and mgr_actions["hands"]:
                for i, hand_act in enumerate(mgr_actions["hands"]):
                    if i < len(actions["hands"]):
                        actions["hands"][i] = hand_act
            
            if "market" in mgr_actions and mgr_actions["market"]:
                actions["market"].extend(mgr_actions["market"])
                
        # 5. Return actions
        return actions

_coordinator_instance = AgentCoordinator()

def agent(obs: dict[str, Any], config: dict[str, Any] = None) -> dict[str, Any]:
    """FieldOps entry point."""
    if not isinstance(obs, dict):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    if getattr(obs, 'step', 0) > 718:
        return {"farmer": ["PASS"], "hands": [], "market": []}
        
    try:
        return _coordinator_instance(obs)
    except Exception as e:
        logger.error(f"Agent crashed: {e}")
        return {"farmer": ["PASS"], "hands": [], "market": []}
