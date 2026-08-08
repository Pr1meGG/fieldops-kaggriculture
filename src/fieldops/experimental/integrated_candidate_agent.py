import logging
from typing import Any

from fieldops.state import ObservationParser
from fieldops.core.planner import DecisionContext
from fieldops.core.economy import EconomicModel

from fieldops.experimental.integrated_candidate_managers import (
    CandidateWorkerManager,
    CandidateEconomyManager,
    CandidateCropManager,
    CandidateMarketManager,
    CandidateLivestockManager
)

from fieldops.observatory.recorder import ObservatoryRecorder

logger = logging.getLogger(__name__)

class IntegratedCandidateAgentCoordinator:
    def __init__(self):
        self.managers = [
            CandidateEconomyManager(),
            CandidateCropManager(),
            CandidateLivestockManager(),
            CandidateWorkerManager(),
            CandidateMarketManager()
        ]
        self.observatory = ObservatoryRecorder()
        self.last_economic_snapshot = None

    def __call__(self, obs: dict[str, Any]) -> dict[str, Any]:
        state = ObservationParser.parse(obs)
        snapshot = EconomicModel.calculate(state, self.last_economic_snapshot)
        self.last_economic_snapshot = snapshot
        
        context = DecisionContext()
        context.economic_snapshot = snapshot
        
        for manager in self.managers:
            manager.initialize(context)
            
        for manager in self.managers:
            manager.update(state, context)
            
        for manager in self.managers:
            manager.plan(state, context)
            
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
                
        return actions

_coordinator_instance = IntegratedCandidateAgentCoordinator()

def integrated_candidate_agent(obs: dict[str, Any], config: dict[str, Any] = None) -> dict[str, Any]:
    if not isinstance(obs, dict):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    if getattr(obs, 'step', 0) > 718:
        try:
            _coordinator_instance.observatory.finalize()
        except Exception as e:
            logger.error(f"Observatory export failed: {e}")
        return {"farmer": ["PASS"], "hands": [], "market": []}

    return _coordinator_instance(obs)
