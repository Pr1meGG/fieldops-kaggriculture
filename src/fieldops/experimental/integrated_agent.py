import logging
from typing import Any

from fieldops.state import ObservationParser
from fieldops.core.planner import DecisionContext
from fieldops.core.economy import EconomicModel
from fieldops.managers.economy_manager import EconomyManager
from fieldops.managers.expansion_manager import ExpansionManager
from fieldops.managers.crop_manager import CropManager
from fieldops.managers.livestock_manager import LivestockManager
from fieldops.managers.market_manager import MarketManager
from fieldops.observatory.recorder import ObservatoryRecorder

from fieldops.experimental.integrated_worker_manager import IntegratedWorkerManager

logger = logging.getLogger(__name__)

class IntegratedAgentCoordinator:
    def __init__(self):
        # Initialize Managers with the IntegratedWorkerManager
        self.managers = [
            EconomyManager(),
            ExpansionManager(),
            IntegratedWorkerManager(),
            CropManager(),
            LivestockManager(),
            MarketManager()
        ]
        self.observatory = ObservatoryRecorder()
        self.last_economic_snapshot = None
        self.hires_ordered = 0
        self.cows_ordered = 0
        self.sheep_ordered = 0
        self.wheat_ordered = 0
        self.seeds_ordered = 0

    def __call__(self, obs: dict[str, Any], hire_worker: bool = False, target_cows: int = 1, target_sheep: int = 1) -> dict[str, Any]:
        state = ObservationParser.parse(obs)
        snapshot = EconomicModel.calculate(state, self.last_economic_snapshot)
        self.last_economic_snapshot = snapshot
        
        # 3. Create DecisionContext & inject snapshot
        context = DecisionContext()
        context.economic_snapshot = snapshot
        
        # Inject targets into the IntegratedWorkerManager
        self.managers[2].target_cows = target_cows
        self.managers[2].target_sheep = target_sheep
        
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
        
        # Hiring strategy
        active_hands = len(state.my_farm.hands) + self.hires_ordered
        target_hands = 1 if hire_worker else 0
        if active_hands < target_hands and state.my_farm.money > 0:
            actions["market"].append(["HIRE"])
            self.hires_ordered += 1
            
        if obs.get("step", 0) == 0:
            self.hires_ordered = 0
            self.cows_ordered = 0
            self.sheep_ordered = 0
            self.wheat_ordered = 0
            self.seeds_ordered = 0
            self.last_money = state.my_farm.money

        self.last_money = state.my_farm.money

        # Livestock Buying Strategy
        my_farm = state.my_farm
        owned_cows = my_farm.shed.items.get("COW", 0) + sum(1 for row in my_farm.tiles for t in row if getattr(t, 'animal', None) == "COW") + self.cows_ordered
        owned_sheep = my_farm.shed.items.get("SHEEP", 0) + sum(1 for row in my_farm.tiles for t in row if getattr(t, 'animal', None) == "SHEEP") + self.sheep_ordered
        pastures = sum(1 for row in my_farm.tiles for t in row if t.kind == "PASTURE")
        
        money = my_farm.money
        animals_to_buy = []
        if owned_cows < target_cows and pastures > (owned_cows + owned_sheep):
            animals_to_buy.append(("COW", target_cows - owned_cows, 400))
        elif owned_sheep < target_sheep and pastures > (owned_cows + owned_sheep):
            animals_to_buy.append(("SHEEP", target_sheep - owned_sheep, 500))

        for anim, count, cost in animals_to_buy:
            if money >= count * cost:
                actions["market"].append(["BUY_ANIMAL", anim, count])
                money -= count * cost
                if anim == "COW": self.cows_ordered += count
                else: self.sheep_ordered += count

        # Feed Buying Strategy
        total_animals = owned_cows + owned_sheep
        wheat_held = my_farm.shed.items.get("WHEAT", 0) + self.wheat_ordered
        all_units = [my_farm.farmer] + list(my_farm.hands)
        for u in all_units:
            wheat_held += u.inventory.items.get("WHEAT", 0)

        if total_animals > 0 and wheat_held < total_animals * 10:
            need_wheat = (total_animals * 10) - wheat_held
            if need_wheat > 0 and money >= need_wheat * 5:
                actions["market"].append(["BUY_PRODUCT", "WHEAT", need_wheat])
                money -= need_wheat * 5
                self.wheat_ordered += need_wheat
                
        # 12-Melon BUY_SEED strategy
        num_seeds_needed = 12 - my_farm.seeds.get("MELON", 0) - sum(1 for row in my_farm.tiles for t in row if getattr(t, 'is_plant', lambda: False)())
        if num_seeds_needed > 0 and money >= num_seeds_needed * 10:
            actions["market"].append(["BUY_SEED", "MELON", num_seeds_needed])
            money -= num_seeds_needed * 10
            
        # SELL strategy
        if my_farm.shed:
            for item, count in my_farm.shed.items.items():
                if count > 0 and item not in ("FERTILIZER", "WHEAT", "COW", "SHEEP"):
                    actions["market"].append(["SELL", item, count])
                
        self.observatory.record_step(state, context, actions, snapshot)
        
        return actions

_coordinator_instance = IntegratedAgentCoordinator()

def integrated_agent(obs: dict[str, Any], config: dict[str, Any] = None) -> dict[str, Any]:
    if not isinstance(obs, dict):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    if getattr(obs, 'step', 0) > 718:
        try:
            _coordinator_instance.observatory.finalize()
        except Exception as e:
            logger.error(f"Observatory export failed: {e}")
        return {"farmer": ["PASS"], "hands": [], "market": []}
        
    hire_worker = config.get("hire_worker", False) if config else False
    target_cows = config.get("target_cows", 0) if config else 0
    target_sheep = config.get("target_sheep", 0) if config else 0
    
    try:
        return _coordinator_instance(obs, hire_worker, target_cows, target_sheep)
    except Exception as e:
        raise e
        return {"farmer": ["PASS"], "hands": [], "market": []}
