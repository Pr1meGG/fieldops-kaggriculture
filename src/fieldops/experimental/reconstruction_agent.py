import logging
from typing import Any

from fieldops.state import ObservationParser
from fieldops.core.planner import DecisionContext
from fieldops.core.economy import EconomicModel
from fieldops.managers.economy_manager import EconomyManager
from fieldops.managers.expansion_manager import ExpansionManager
from fieldops.managers.worker_manager import HybridWorkerManager
from fieldops.managers.crop_manager import CropManager
from fieldops.managers.livestock_manager import LivestockManager
from fieldops.managers.market_manager import MarketManager
from fieldops.observatory.recorder import ObservatoryRecorder

logger = logging.getLogger(__name__)

class ReconstructionConfig:
    def __init__(self, **kwargs):
        self.LIQUIDATE_STARTING_WHEAT = kwargs.get('LIQUIDATE_STARTING_WHEAT', False)
        self.AGGRESSIVE_REINVESTMENT = kwargs.get('AGGRESSIVE_REINVESTMENT', False)
        self.DYNAMIC_WORKERS = kwargs.get('DYNAMIC_WORKERS', False)
        self.DYNAMIC_LAND = kwargs.get('DYNAMIC_LAND', False)
        self.WHEAT_EARLY_GAME = kwargs.get('WHEAT_EARLY_GAME', False)
        self.MELON_MID_GAME = kwargs.get('MELON_MID_GAME', False)
        self.STRAWBERRY_LATE_GAME = kwargs.get('STRAWBERRY_LATE_GAME', False)
        self.LIVESTOCK = kwargs.get('LIVESTOCK', False)
        self.FERTILIZER = kwargs.get('FERTILIZER', False)
        self.COMPACT_SPATIAL_LAYOUT = kwargs.get('COMPACT_SPATIAL_LAYOUT', False)
        self.OBSERVED_SELLING = kwargs.get('OBSERVED_SELLING', False)

class ReconstructionAgentCoordinator:
    def __init__(self, config: ReconstructionConfig):
        self.config = config
        self.managers = [
            EconomyManager(),
            ExpansionManager(),
            HybridWorkerManager(), # Control uses Hybrid
            CropManager(),
            LivestockManager(),
            MarketManager()
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
        
        my_farm = state.my_farm
        step = obs.get("step", 0)

        # ----------------------------------------------------
        # FEATURE: LIQUIDATE_STARTING_WHEAT
        # ----------------------------------------------------
        if self.config.LIQUIDATE_STARTING_WHEAT and step == 0:
            wheat_count = my_farm.shed.items.get("WHEAT", 0)
            if wheat_count > 0:
                actions["market"].append(["SELL", "WHEAT", wheat_count])
                
        # ----------------------------------------------------
        # FEATURE: AGGRESSIVE_REINVESTMENT
        # ----------------------------------------------------
        cash_reserve = 0 if self.config.AGGRESSIVE_REINVESTMENT else 500

        # Calculate current capacity and workload
        # A rough heuristic: 1 worker handles ~6 crop tiles comfortably.
        num_plants = sum(1 for row in my_farm.tiles for t in row if isinstance(t, dict) and t.get('kind') == 'PLANT' or (not isinstance(t, dict) and t.is_plant()))
        num_weeds = sum(1 for row in my_farm.tiles for t in row if isinstance(t, dict) and t.get('kind') == 'WEED' or (not isinstance(t, dict) and t.is_weed()))
        total_land = len(my_farm.tiles) // 4
        num_workers = len(my_farm.hands)
        workload = num_plants + num_weeds
        
        # ----------------------------------------------------
        # FEATURE: DYNAMIC_WORKERS
        # ----------------------------------------------------
        current_money = my_farm.money
        if self.config.DYNAMIC_WORKERS:
            # If workload exceeds our capacity (6 tiles per worker), hire.
            if workload > num_workers * 6 and current_money >= 100 + cash_reserve:
                actions["market"].append(["HIRE"])
                current_money -= 100 # local state update for next checks
        else:
            # 2-worker strategy
            if step == 0 and num_workers < 1:
                actions["market"].append(["HIRE"])
                current_money -= 100

        # ----------------------------------------------------
        # FEATURE: DYNAMIC_LAND
        # ----------------------------------------------------
        if self.config.DYNAMIC_LAND:
            # If we are utilizing almost all our land, buy more.
            # Land cost increases linearly: 500, 1000, 1500, etc.
            # We don't have exact land cost without the formula, but we can assume starting at 500.
            # In fieldops, BUY_LAND doesn't specify price, we just issue it. We'll issue if we have > 1000 to be safe, or just check.
            # Actually, `ExpansionManager` knows the cost, but we can just use a proxy.
            if num_plants >= total_land * 0.8 and current_money >= 1000 + cash_reserve:
                actions["market"].append(["BUY_LAND"])
                current_money -= 1000 # rough deduct

        if not self.config.WHEAT_EARLY_GAME and not self.config.MELON_MID_GAME and not self.config.STRAWBERRY_LATE_GAME:
            # 12-Melon strategy baseline OR Dynamic Reinvestment if enabled
            # If dynamic land/workers are enabled, we should also buy seeds for the new capacity!
            target_melons = 12
            if self.config.AGGRESSIVE_REINVESTMENT:
                target_melons = total_land # plant all available land if aggressive!
                
            num_seeds_needed = target_melons - my_farm.seeds.get("MELON", 0) - num_plants
            if num_seeds_needed > 0 and current_money >= num_seeds_needed * 10 + cash_reserve:
                actions["market"].append(["BUY_SEED", "MELON", num_seeds_needed])
                
        if not self.config.OBSERVED_SELLING:
            # Baseline sell all non-fertilizer
            if my_farm.shed:
                for item, count in my_farm.shed.items.items():
                    if count > 0 and item != "FERTILIZER":
                        # Ensure we don't duplicate sell actions from LIQUIDATE_STARTING_WHEAT
                        if not (self.config.LIQUIDATE_STARTING_WHEAT and step == 0 and item == "WHEAT"):
                            actions["market"].append(["SELL", item, count])
                            
        self.observatory.record_step(state, context, actions, snapshot)
        return actions

def agent_factory(config_dict=None):
    cfg = ReconstructionConfig(**(config_dict or {}))
    coordinator = ReconstructionAgentCoordinator(cfg)
    def _agent(obs):
        return coordinator(obs)
    return _agent
