from typing import Any
from fieldops.observatory.metrics import EconomyMetrics, WorkerMetrics, LandMetrics, CropMetrics, LivestockMetrics, MarketMetrics
from fieldops.observatory.events import Event
from fieldops.observatory.exporter import ObservatoryExporter

class ObservatoryRecorder:
    def __init__(self, seed=0):
        self.seed = seed
        self.timeline = []
        
        self.economy = EconomyMetrics()
        self.workers = {}
        self.land = LandMetrics()
        self.crops = {}
        self.livestock = {}
        self.market = MarketMetrics()
        
        self.decision_log = []
        self.event_log = []
        
        self.exporter = ObservatoryExporter()
        
    def get_stable_id(self, entity_type, x, y, spawn_turn=None):
        base_id = f"{entity_type}_{x}_{y}"
        if spawn_turn is not None:
            base_id += f"_t{spawn_turn}"
        return base_id

    def record_step(self, state, context, actions):
        turn = state.day * 24 + state.hour
        
        # 1. Update Metrics (Passive observation)
        self._update_economy(state, actions)
        self._update_workers(state, actions)
        self._update_land(state)
        self._update_crops_livestock(state, actions, turn)
        self._update_market(state, actions)
        
        # 2. Append decisions and events
        self.decision_log.extend(context.decision_log)
        context.decision_log.clear() # Safe to clear as context is rebuilt per turn in agent.py
        
        # 3. Snapshot for per-turn timeline
        snapshot = {
            "turn": turn,
            "day": state.day,
            "hour": state.hour,
            "cash": state.my_farm.money,
            "actions": actions,
        }
        self.timeline.append(snapshot)
        
    def _update_economy(self, state, actions):
        self.economy.cash = state.my_farm.money
        # In a fully implemented state parser, we'd tally actual land costs.
        # For now, this serves as the foundational skeleton.
        self.economy.capital_locked_land = sum(3000 for q in range(1, 4) if getattr(state.my_farm, f"quadrant_{q}", False))
        
    def _update_workers(self, state, actions):
        # We assume state.my_farm.farmer and hands exist in a full parser.
        # This function will passively read their state without modifying it.
        pass 
        
    def _update_land(self, state):
        tiles = [t for row in getattr(state.my_farm, 'tiles', []) for t in row]
        self.land.total_tiles = len(tiles)
        
    def _update_crops_livestock(self, state, actions, turn):
        pass

    def _update_market(self, state, actions):
        pass

    def finalize(self):
        data = {
            "timeline": self.timeline,
            "economy": self.economy.__dict__,
            "land": self.land.__dict__,
            "decisions": self.decision_log,
            "events": [e.__dict__ for e in self.event_log]
        }
        self.exporter.export_game(self.seed, data)
