from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class EconomyMetrics:
    cash: int = 0
    earned: int = 0
    spent: int = 0
    running_profit: int = 0
    inventory_value: int = 0
    capital_locked_land: int = 0
    capital_locked_crops: int = 0
    capital_locked_livestock: int = 0
    capital_locked_inventory: int = 0
    investment_history: List[dict] = field(default_factory=list)

@dataclass
class WorkerMetrics:
    id: str = ""
    idle_time: int = 0
    walking_time: int = 0
    working_time: int = 0
    harvest_time: int = 0
    planting_time: int = 0
    watering_time: int = 0
    weed_removal_time: int = 0
    waiting_time: int = 0
    travel_distance: int = 0
    current_assignment: str = ""
    assignment_completion_time: int = 0

@dataclass
class LandMetrics:
    total_tiles: int = 0
    unlocked_tiles: int = 0
    utilized_tiles: int = 0
    idle_tiles: int = 0
    empty_tiles: int = 0
    weed_tiles: int = 0
    utilization_pct: float = 0.0
    quadrant_utilization: Dict[int, float] = field(default_factory=dict)

@dataclass
class CropMetrics:
    seeds_bought: int = 0
    seeds_planted: int = 0
    harvests: int = 0
    deaths: int = 0
    revenue: int = 0
    profit: int = 0
    lifecycles: List[int] = field(default_factory=list)
    yields: List[int] = field(default_factory=list)
    
    @property
    def average_lifecycle(self):
        return sum(self.lifecycles)/len(self.lifecycles) if self.lifecycles else 0
        
    @property
    def average_yield(self):
        return sum(self.yields)/len(self.yields) if self.yields else 0

@dataclass
class LivestockMetrics:
    animals: int = 0
    feed_consumed: int = 0
    maintenance_cost: int = 0
    revenue: int = 0
    profit: int = 0

@dataclass
class MarketMetrics:
    items_sold: int = 0
    revenue: int = 0
    unsold_inventory: int = 0
    prices: List[int] = field(default_factory=list)
    inventory_history: List[dict] = field(default_factory=list)

    @property
    def average_selling_price(self):
        return sum(self.prices)/len(self.prices) if self.prices else 0
