
from abc import ABC, abstractmethod

class DecisionContext:
    def __init__(self):
        self.worker_reservations = []
        self.tile_reservations = []
        self.planned_investments = []
        self.decision_log = []

    def log_decision(self, decision_id, manager, action, reason="Not Implemented", alternatives=None, expected_roi=0, confidence=0, timestamp=None):
        self.decision_log.append({
            "Decision ID": decision_id,
            "Manager": manager,
            "Action": action,
            "Reason": reason,
            "Alternatives": alternatives or [],
            "Expected ROI": expected_roi,
            "Confidence": confidence,
            "Timestamp": timestamp
        })

class BaseManager(ABC):
    @abstractmethod
    def initialize(self, context: DecisionContext):
        pass

    @abstractmethod
    def update(self, state, context: DecisionContext):
        pass

    @abstractmethod
    def plan(self, state, context: DecisionContext):
        pass

    @abstractmethod
    def execute(self, state, context: DecisionContext) -> dict:
        pass
