
from abc import ABC, abstractmethod

class DecisionContext:
    def __init__(self):
        self.worker_reservations = []
        self.tile_reservations = []
        self.planned_investments = []

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
