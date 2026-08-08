import logging
from typing import Any

from fieldops.state import ObservationParser
from fieldops.core.planner import DecisionContext
from fieldops.core.economy import EconomicModel
from fieldops.managers.economy_manager import EconomyManager
from fieldops.managers.expansion_manager import ExpansionManager
from fieldops.managers.worker_manager import HybridWorkerManager, HybridDigWorkerManager, V2WorkerManager
from fieldops.managers.crop_manager import CropManager
from fieldops.managers.livestock_manager import LivestockManager
from fieldops.managers.market_manager import MarketManager
from fieldops.observatory.recorder import ObservatoryRecorder

logger = logging.getLogger(__name__)

class AgentCoordinator:
    def __init__(self):
        # Initialize Managers
        self.managers = [
            EconomyManager(),
            ExpansionManager(),
            HybridWorkerManager(), # Default to Hybrid, can be swapped
            CropManager(),
            LivestockManager(),
            MarketManager()
        ]
        self.observatory = ObservatoryRecorder()
        self.last_economic_snapshot = None

    def __call__(self, obs: dict[str, Any]) -> dict[str, Any]:
        # 1. Read Observation & Build GameState
        state = ObservationParser.parse(obs)
        # 2. Economic Snapshot (Phase 2)
        snapshot = EconomicModel.calculate(state, self.last_economic_snapshot)
        self.last_economic_snapshot = snapshot
        
        # 3. Create DecisionContext & inject snapshot
        context = DecisionContext()
        context.economic_snapshot = snapshot
        
        # 4. Call Managers (Initialize, Update, Plan)
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
        
        # Hardcoded 2-worker strategy (Hire 1 hand on step 0)
        if obs.get("step", 0) == 0:
            actions["market"].append(["HIRE"])
            
        # Hardcoded 12-Melon BUY_SEED strategy
        my_farm = state.my_farm
        num_seeds_needed = 12 - my_farm.seeds.get("MELON", 0) - sum(1 for row in my_farm.tiles for t in row if t.is_plant())
        if num_seeds_needed > 0 and my_farm.money >= num_seeds_needed * 10:
            actions["market"].append(["BUY_SEED", "MELON", num_seeds_needed])
            
        # Hardcoded SELL strategy
        if my_farm.shed:
            for item, count in my_farm.shed.items.items():
                if count > 0 and item != "FERTILIZER":
                    actions["market"].append(["SELL", item, count])
                
        # 5. Passive observation
        self.observatory.record_step(state, context, actions, snapshot)
        
        # 6. Return actions
        return actions

_coordinator_instance = AgentCoordinator()

def agent(obs: dict[str, Any], config: dict[str, Any] = None) -> dict[str, Any]:
    """FieldOps entry point."""
    if config and "scheduler_version" in config:
        if config.get("scheduler_version") == "V1":
            _coordinator_instance.managers[2] = HybridWorkerManager()
        elif config.get("scheduler_version") == "Hybrid":
            _coordinator_instance.managers[2] = HybridWorkerManager()
        elif config.get("scheduler_version") == "Hybrid_DIG":
            _coordinator_instance.managers[2] = HybridDigWorkerManager()
        elif config.get("scheduler_version") == "V2":
            _coordinator_instance.managers[2] = V2WorkerManager()
    if not isinstance(obs, dict):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    if getattr(obs, 'step', 0) > 718:
        try:
            _coordinator_instance.observatory.finalize()
        except Exception as e:
            logger.error(f"Observatory export failed: {e}")
        return {"farmer": ["PASS"], "hands": [], "market": []}
        
    try:
        return _coordinator_instance(obs)
    except Exception as e:
        raise e
        return {"farmer": ["PASS"], "hands": [], "market": []}
