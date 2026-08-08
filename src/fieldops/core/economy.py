from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Optional, Dict

from fieldops.state import GameState
from fieldops.constants import CROP_DATA, ANIMAL_DATA

@dataclass(frozen=True)
class EconomicSnapshot:
    """Immutable single-turn economic observation of the game state."""
    
    # Asset Values
    cash: int
    
    inventory_cost_basis: int
    inventory_market_value: int
    
    livestock_cost_basis: int
    livestock_market_value: int
    
    land_cost_basis: int
    land_value: int
    
    # Aggregates
    total_cost_basis: int
    total_market_value: int
    total_wealth: int
    
    # Market Telemetry (Immutable mappings for offline analysis)
    market_prices: MappingProxyType[str, int]
    market_inventory: MappingProxyType[str, int]
    market_prices_delta: MappingProxyType[str, int]
    market_inventory_delta: MappingProxyType[str, int]
    
    # Flow Metrics (Calculated via historical delta)
    net_cash_change: int
    delta_wealth: int
    delta_inventory_value: int
    
    # Productivity Metrics
    wealth_per_worker: float
    wealth_per_tile: float


class EconomicModel:
    """Stateless model that derives EconomicSnapshot from GameState."""
    
    @staticmethod
    def calculate(state: GameState, previous: Optional[EconomicSnapshot] = None) -> EconomicSnapshot:
        # 1. Cash
        cash = state.my_farm.money
        
        # 2. Inventory Valuation
        inv_cost_basis = 0
        inv_market_value = 0
        
        shed_items = state.my_farm.shed.items if getattr(state.my_farm, "shed", None) else {}
        
        for item, qty in shed_items.items():
            # Cost Basis
            if item in CROP_DATA:
                inv_cost_basis += CROP_DATA[item].get("seed_cost", 0) * qty
            elif item in ANIMAL_DATA:
                inv_cost_basis += ANIMAL_DATA[item].get("purchase_cost", 0) * qty
                
            # Market Value
            # Observe real-time price if available, otherwise use deterministic base_price fallback
            fallback_price = 0
            if item in CROP_DATA:
                fallback_price = CROP_DATA[item].get("base_price", 0)
            elif item in ANIMAL_DATA:
                fallback_price = ANIMAL_DATA[item].get("base_price", 0)
                
            current_price = state.market.prices.get(item, fallback_price)
            inv_market_value += current_price * qty
            
        # Seeds in inventory count towards cost basis but have no liquidation market value 
        # (Assuming they cannot be sold back based on typical game rules).
        seed_items = state.my_farm.seeds if getattr(state.my_farm, "seeds", None) else {}
        for seed_item, qty in seed_items.items():
            if seed_item in CROP_DATA:
                inv_cost_basis += CROP_DATA[seed_item].get("seed_cost", 0) * qty
            
        # 3. Livestock Valuation
        live_cost_basis = 0
        live_market_value = 0
        
        for row in getattr(state.my_farm, "tiles", []):
            for tile in row:
                if getattr(tile, "animal", None) is not None:
                    species = tile.animal
                    if species in ANIMAL_DATA:
                        live_cost_basis += ANIMAL_DATA[species].get("purchase_cost", 0)
                        # Animals typically do not have a liquidation value unless stated.
                        # Documented limitation: Cannot sell adult animals in standard game. Market value is 0.
                        live_market_value += 0
                
        # 4. Land Valuation
        land_cost_basis = 0
        
        # Quadrants unlocked
        unlocked = getattr(state.my_farm, "unlocked_quadrants", ["NW"])
        # NW is free, others cost 3000
        land_cost_basis = max(0, len(unlocked) - 1) * 3000
                
        # Documented limitation: Land cannot be sold back, so liquidation value is 0.
        land_value = 0
        
        # 5. Aggregates
        total_cost_basis = cash + inv_cost_basis + live_cost_basis + land_cost_basis
        total_market_value = inv_market_value + live_market_value + land_value
        total_wealth = cash + total_market_value
        
        # 6. Market Telemetry
        market_prices = MappingProxyType(state.market.prices.copy())
        market_inventory = MappingProxyType(state.market.inventory.copy())
        
        prices_delta = {}
        inventory_delta = {}
        
        if previous:
            for k in market_prices:
                prices_delta[k] = market_prices[k] - previous.market_prices.get(k, market_prices[k])
            for k in market_inventory:
                inventory_delta[k] = market_inventory[k] - previous.market_inventory.get(k, market_inventory[k])
                
        market_prices_delta = MappingProxyType(prices_delta)
        market_inventory_delta = MappingProxyType(inventory_delta)
        
        # 7. Flow Metrics
        net_cash_change = 0
        delta_wealth = 0
        delta_inventory_value = 0
        
        if previous:
            net_cash_change = cash - previous.cash
            delta_wealth = total_wealth - previous.total_wealth
            delta_inventory_value = inv_market_value - previous.inventory_market_value
            
        # 8. Productivity
        num_workers = 1 + len(state.my_farm.hands)
        
        # Calculate total tiles unlocked
        unlocked = getattr(state.my_farm, "unlocked_quadrants", ["NW"])
        num_tiles = len(unlocked) * 100
            
        wealth_per_worker = float(total_wealth) / num_workers if num_workers > 0 else 0.0
        wealth_per_tile = float(total_wealth) / num_tiles if num_tiles > 0 else 0.0
        
        return EconomicSnapshot(
            cash=cash,
            inventory_cost_basis=inv_cost_basis,
            inventory_market_value=inv_market_value,
            livestock_cost_basis=live_cost_basis,
            livestock_market_value=live_market_value,
            land_cost_basis=land_cost_basis,
            land_value=land_value,
            total_cost_basis=total_cost_basis,
            total_market_value=total_market_value,
            total_wealth=total_wealth,
            market_prices=market_prices,
            market_inventory=market_inventory,
            market_prices_delta=market_prices_delta,
            market_inventory_delta=market_inventory_delta,
            net_cash_change=net_cash_change,
            delta_wealth=delta_wealth,
            delta_inventory_value=delta_inventory_value,
            wealth_per_worker=wealth_per_worker,
            wealth_per_tile=wealth_per_tile
        )
