"""
A/B/C Selling Policy Benchmark.

Runs 20 simulations each for three selling policies:
  A) Sell everything immediately (current behavior)
  B) Rate-limited: sell only enough to keep melon price >= $200
  C) Adaptive: decide each turn whether selling or waiting yields more money,
     considering town/shop consumption, shed capacity, future harvests, cash needs

Reports all requested metrics from raw simulator data.
"""
import sys, os, math, statistics, copy
sys.path.insert(0, os.path.abspath("src"))

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture.kaggriculture import (
    market_price, MARKET_PARAMS, CROPS, SHOPS,
    TOWN_CENTER_PRODUCTS, TOWN_CENTER_DEMAND_SCHEDULE,
)
from fieldops.state import ObservationParser, Position
from fieldops.constants import SHED_ADJACENT_TILES, CROP_DATA

# ──────────────────────────────────────────────────────────────────────
# Exact market price function (re-exported for convenience)
# ──────────────────────────────────────────────────────────────────────

def exact_melon_price(inventory):
    return market_price("MELON", inventory, MARKET_PARAMS)

# ──────────────────────────────────────────────────────────────────────
# Town/shop consumption model (exact from kaggriculture.py)
# ──────────────────────────────────────────────────────────────────────

def estimate_town_consumption_per_turn(step, unlocked_shops):
    """How many melon units the town drains from market inventory this turn."""
    consumed = 0
    shop_interval = 4
    center_interval = 12
    turns_per_day = 24
    day = step // turns_per_day

    # Town center
    if step % center_interval == 0:
        center_mult = next(m for threshold, m in TOWN_CENTER_DEMAND_SCHEDULE if day >= threshold)
        consumed += center_mult  # for MELON specifically

    # Shops
    if step % shop_interval == 0:
        for shop_name in unlocked_shops:
            products = SHOPS[shop_name]
            if "MELON" in products:
                mult = 2 if len(products) == 1 else 1
                consumed += mult

    return consumed

# ──────────────────────────────────────────────────────────────────────
# Helper functions shared by all policies
# ──────────────────────────────────────────────────────────────────────

def _distance(p1, p2):
    return abs(p1.x - p2.x) + abs(p1.y - p2.y)

def _choose_movement(current, target):
    dx = target.x - current.x
    dy = target.y - current.y
    if abs(dx) > abs(dy):
        return "EAST" if dx > 0 else "WEST"
    elif dy != 0:
        return "SOUTH" if dy > 0 else "NORTH"
    elif dx != 0:
        return "EAST" if dx > 0 else "WEST"
    return "PASS"

def _fib(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a

# ──────────────────────────────────────────────────────────────────────
# Agent with configurable selling policy
# ──────────────────────────────────────────────────────────────────────

class BenchmarkAgent:
    def __init__(self, sell_policy="A"):
        self.sell_policy = sell_policy
        # Track planted crops for Policy C future harvest estimation
        self.planted_tiles = {}  # (x,y) -> (crop, planted_day)

    def __call__(self, obs):
        # Handle edge case: step 719 is the final observation, no actions needed
        step = obs.get('step', 0) if isinstance(obs, dict) else getattr(obs, 'step', 0)
        if step >= 719:
            return {"farmer": ["PASS"], "hands": [], "market": []}

        state = ObservationParser.parse(obs)
        my_farm = state.my_farm

        actions = {"farmer": ["PASS"], "hands": [], "market": []}

        # ── SELLING ──
        if my_farm.shed is not None:
            if self.sell_policy == "A":
                self._sell_policy_a(state, my_farm, actions)
            elif self.sell_policy == "B":
                self._sell_policy_b(state, my_farm, actions)
            elif self.sell_policy == "C":
                self._sell_policy_c(state, my_farm, actions)

        # ── LAND PURCHASE ──
        quads_unlocked = len(my_farm.unlocked_quadrants)
        if quads_unlocked < 4:
            land_cost = 1000 if quads_unlocked == 1 else (2000 if quads_unlocked == 2 else 4000)
            seed_buffer = 25 * CROP_DATA["MELON"]["seed_cost"]
            worker_buffer = 100
            if my_farm.money >= (land_cost + seed_buffer + worker_buffer) and state.day <= 18:
                actions["market"].append(["BUY_LAND"])

        # ── HIRING ──
        target_hands = min(5, quads_unlocked + 1)
        if my_farm.hires_today < target_hands and my_farm.money >= 50:
            actions["market"].append(["HIRE"])

        # ── SEED PURCHASE ──
        empty_unlocked_tiles = [
            Position(x=x, y=y)
            for y, row in enumerate(my_farm.tiles)
            for x, tile in enumerate(row)
            if tile.is_empty()
        ]
        num_empty = len(empty_unlocked_tiles)
        target_crop = "MELON" if state.step <= 408 else ("CARROT" if state.step <= 600 else None)

        if target_crop is not None and num_empty > 0:
            current_seeds = my_farm.seeds.get(target_crop) if my_farm.seeds else 0
            needed_seeds = num_empty - current_seeds
            if needed_seeds > 0:
                seed_cost = CROP_DATA[target_crop]["seed_cost"]
                buy_qty = min(needed_seeds, int(my_farm.money // seed_cost))
                if buy_qty > 0:
                    actions["market"].append(["BUY_SEED", target_crop, buy_qty])

        # ── UNIT SCHEDULER ──
        max_melon_day = CROP_DATA["MELON"]["max_yield_day"]
        max_carrot_day = CROP_DATA["CARROT"]["max_yield_day"]

        unwatered_tiles = []
        harvestable_tiles = []
        empty_tiles = []

        for y, row in enumerate(my_farm.tiles):
            for x, tile in enumerate(row):
                pos = Position(x=x, y=y)
                if tile.kind == "PLANT":
                    max_day = max_melon_day if tile.crop == "MELON" else max_carrot_day
                    if tile.planted_day is not None and (state.day - tile.planted_day) >= max_day:
                        harvestable_tiles.append(pos)
                    elif not tile.watered_today:
                        unwatered_tiles.append(pos)
                    # Track for Policy C
                    if tile.planted_day is not None:
                        self.planted_tiles[(x, y)] = (tile.crop, tile.planted_day)
                elif tile.is_empty():
                    empty_tiles.append(pos)
                    self.planted_tiles.pop((x, y), None)

        shed_tiles = [Position(x=x, y=y) for x, y in SHED_ADJACENT_TILES]
        all_units = [my_farm.farmer] + list(my_farm.hands)
        unit_actions = []
        targeted_tiles = set()

        melon_seeds_avail = my_farm.seeds.get("MELON") if my_farm.seeds else 0
        carrot_seeds_avail = my_farm.seeds.get("CARROT") if my_farm.seeds else 0
        melon_reserved = 0
        carrot_reserved = 0

        for unit in all_units:
            valid_water = [p for p in unwatered_tiles if p not in targeted_tiles]
            if valid_water:
                target = min(valid_water, key=lambda p: _distance(unit.position, p))
                targeted_tiles.add(target)
                if unit.position == target:
                    action = ["WATER"]
                else:
                    action = [_choose_movement(unit.position, target)]
                unit_actions.append(action)
                continue

            valid_harvest = [p for p in harvestable_tiles if p not in targeted_tiles]
            if valid_harvest:
                target = min(valid_harvest, key=lambda p: _distance(unit.position, p))
                targeted_tiles.add(target)
                if unit.position == target:
                    action = ["HARVEST"]
                else:
                    action = [_choose_movement(unit.position, target)]
                unit_actions.append(action)
                continue

            has_produce = any(count > 0 for item, count in unit.inventory.items.items() if item != "FERTILIZER")
            if has_produce:
                target = min(shed_tiles, key=lambda p: _distance(unit.position, p))
                if unit.position in shed_tiles:
                    action = ["DROP"]
                else:
                    action = [_choose_movement(unit.position, target)]
                unit_actions.append(action)
                continue

            valid_empty = [p for p in empty_tiles if p not in targeted_tiles]
            if valid_empty:
                if (melon_seeds_avail - melon_reserved) > 0:
                    target = min(valid_empty, key=lambda p: _distance(unit.position, p))
                    targeted_tiles.add(target)
                    melon_reserved += 1
                    if unit.position == target:
                        action = ["PLANT", "MELON"]
                    else:
                        action = [_choose_movement(unit.position, target)]
                    unit_actions.append(action)
                    continue
                elif (carrot_seeds_avail - carrot_reserved) > 0:
                    target = min(valid_empty, key=lambda p: _distance(unit.position, p))
                    targeted_tiles.add(target)
                    carrot_reserved += 1
                    if unit.position == target:
                        action = ["PLANT", "CARROT"]
                    else:
                        action = [_choose_movement(unit.position, target)]
                    unit_actions.append(action)
                    continue

            unit_actions.append(["PASS"])

        actions["farmer"] = unit_actions[0]
        actions["hands"] = unit_actions[1:]
        return actions

    # ── POLICY A: Sell everything immediately ──
    def _sell_policy_a(self, state, my_farm, actions):
        for item, count in my_farm.shed.items.items():
            if count > 0 and item != "FERTILIZER":
                actions["market"].append(["SELL", item, count])

    # ── POLICY B: Rate-limited, keep melon price >= $200 ──
    def _sell_policy_b(self, state, my_farm, actions):
        for item, count in my_farm.shed.items.items():
            if count <= 0 or item == "FERTILIZER":
                continue
            if item != "MELON":
                actions["market"].append(["SELL", item, count])
                continue
            # Find max n where price after selling n >= floor_price
            current_inv = state.market.inventory.get("MELON", 10000)
            floor_price = 200
            sell_n = 0
            for n in range(1, count + 1):
                p = exact_melon_price(current_inv + n)
                if p >= floor_price:
                    sell_n = n
                else:
                    break
            if sell_n > 0:
                actions["market"].append(["SELL", "MELON", sell_n])

    # ── POLICY C: Adaptive forward-looking ──
    def _sell_policy_c(self, state, my_farm, actions):
        for item, count in my_farm.shed.items.items():
            if count <= 0 or item == "FERTILIZER":
                continue
            if item != "MELON":
                actions["market"].append(["SELL", item, count])
                continue

            current_inv = state.market.inventory.get("MELON", 10000)
            current_step = state.step
            remaining_steps = 719 - current_step
            shed_count = count
            shed_capacity = 100
            total_shed_items = sum(v for v in my_farm.shed.items.values())

            # Estimate future melon arrivals from planted crops
            future_harvests = 0
            for (x, y), (crop, planted_day) in self.planted_tiles.items():
                if crop != "MELON":
                    continue
                harvest_day = planted_day + CROP_DATA["MELON"]["max_yield_day"]
                if harvest_day > state.day:
                    future_harvests += 6  # max_yield_unf per melon tile

            # Estimate town consumption over next 48 steps (2 days)
            town_shops = state.town_shops if hasattr(state, 'town_shops') else []
            # We don't have exact shop list, estimate conservatively
            town_drain_per_day = 2 + 1  # center (1-4 per 12 turns) + some shops

            # Decision: sell now vs wait
            # If shed is getting full (>80%), sell more aggressively
            shed_pressure = total_shed_items / shed_capacity

            # Compute revenue from selling all now
            rev_now = 0
            inv_sim = current_inv
            for _ in range(shed_count):
                p = exact_melon_price(inv_sim)
                rev_now += p
                if p > 1:
                    inv_sim += 1

            # Compute revenue from selling half now, half in 24 steps
            # After 24 steps, town drains ~town_drain_per_day from inventory
            half = max(1, shed_count // 2)
            rev_half_now = 0
            inv_sim2 = current_inv
            for _ in range(half):
                p = exact_melon_price(inv_sim2)
                rev_half_now += p
                if p > 1:
                    inv_sim2 += 1

            # Inventory after town drain (1 day = ~3 units drained for melon)
            inv_later = max(0, inv_sim2 - town_drain_per_day)
            remainder = shed_count - half
            rev_later = 0
            for _ in range(remainder):
                p = exact_melon_price(inv_later)
                rev_later += p
                if p > 1:
                    inv_later += 1

            rev_split = rev_half_now + rev_later

            # Check cash needs: do we need money for seeds/land/hires?
            cash_needed = 0
            quads = len(my_farm.unlocked_quadrants)
            if quads < 4:
                land_cost = 1000 if quads == 1 else (2000 if quads == 2 else 4000)
                cash_needed += land_cost + 2000 + 100

            # Decision
            if shed_pressure > 0.8 or remaining_steps < 48:
                # Sell everything - shed full or game ending
                sell_n = shed_count
            elif rev_split > rev_now * 1.03:
                # Splitting is at least 3% better
                sell_n = half
            elif cash_needed > 0 and my_farm.money < cash_needed:
                # Need cash for investment
                # Sell enough to cover cash needs
                needed_rev = cash_needed - my_farm.money
                sell_n = 0
                inv_sim3 = current_inv
                for i in range(shed_count):
                    p = exact_melon_price(inv_sim3)
                    sell_n += 1
                    needed_rev -= p
                    if p > 1:
                        inv_sim3 += 1
                    if needed_rev <= 0:
                        break
            else:
                # Default: sell only if price is good
                floor_price = 180
                sell_n = 0
                for n in range(1, shed_count + 1):
                    p = exact_melon_price(current_inv + n)
                    if p >= floor_price:
                        sell_n = n
                    else:
                        break

            if sell_n > 0:
                actions["market"].append(["SELL", "MELON", sell_n])


# ──────────────────────────────────────────────────────────────────────
# Simulation runner with full instrumentation
# ──────────────────────────────────────────────────────────────────────

def run_simulation(policy, seed=None):
    """Run one episode, return dict of metrics."""
    env = make("kaggriculture", debug=True,
               configuration={"episodeSteps": 721, "agentTimeout": 600})
    if seed is not None:
        env.configuration.seed = seed

    agent_inst = BenchmarkAgent(sell_policy=policy)

    def agent_fn(obs, cfg=None):
        return agent_inst(obs)

    steps = env.run([agent_fn, "pass"])

    # ── Collect metrics ──
    total_melons_sold = 0
    total_revenue = 0
    total_sell_events = 0
    sell_prices = []
    shed_levels = []
    market_inv_curve = []
    shed_overflow = 0
    total_planted = 0
    total_harvested = 0
    harvest_units_collected = 0

    for i, step in enumerate(steps):
        obs_dict = step[0].observation
        step_num = obs_dict.get('step', 0)
        if step_num >= 719:
            continue

        # Market inventory tracking
        market = obs_dict.get('market', {})
        melon_inv = market.get('inventory', {}).get('MELON', 10000)
        market_inv_curve.append((step_num, melon_inv))

        # Shed level tracking
        private = obs_dict.get('private', {})
        shed = private.get('shed', {})
        shed_total = sum(v for v in shed.values())
        shed_levels.append(shed_total)
        if shed_total >= 100:
            shed_overflow += 1

        action = step[0].action
        if not action:
            continue

        market_acts = action.get("market", [])
        for m in market_acts:
            if not m:
                continue
            if m[0] == "SELL" and m[1] == "MELON":
                qty = m[2]
                total_melons_sold += qty
                total_sell_events += 1
                price = market.get('prices', {}).get('MELON', 250)
                sell_prices.append(price)
                total_revenue += qty * price  # approximate (actual is per-unit)

        unit_acts = [action.get("farmer", ["PASS"])] + action.get("hands", [])
        for act in unit_acts:
            if not act:
                continue
            if act[0] == "PLANT":
                total_planted += 1
            elif act[0] == "HARVEST":
                total_harvested += 1

    final_reward = steps[-1][0].reward
    final_money = steps[-1][0].observation['farms'][0]['money']

    avg_sell_price = statistics.mean(sell_prices) if sell_prices else 0
    avg_shed = statistics.mean(shed_levels) if shed_levels else 0

    return {
        "reward": final_reward,
        "money": final_money,
        "melons_sold": total_melons_sold,
        "total_revenue_approx": total_revenue,
        "avg_sell_price": avg_sell_price,
        "avg_shed_level": avg_shed,
        "shed_overflow_turns": shed_overflow,
        "total_planted": total_planted,
        "total_harvested": total_harvested,
        "market_inv_final": market_inv_curve[-1][1] if market_inv_curve else 10000,
        "sell_events": total_sell_events,
    }


def run_benchmark(policy, n_runs=20):
    """Run n simulations and aggregate."""
    results = []
    for seed in range(1, n_runs + 1):
        r = run_simulation(policy, seed=seed)
        results.append(r)
        print(f"  Policy {policy} seed {seed:2d}: reward=${r['reward']:,.0f}  "
              f"melons_sold={r['melons_sold']}  avg_price=${r['avg_sell_price']:.0f}  "
              f"shed_overflow={r['shed_overflow_turns']}  planted={r['total_planted']}  "
              f"harvested={r['total_harvested']}")
    return results


def report(policy, results):
    """Print aggregate statistics."""
    rewards = [r["reward"] for r in results]
    prices = [r["avg_sell_price"] for r in results]
    shed_levels = [r["avg_shed_level"] for r in results]
    melons = [r["melons_sold"] for r in results]
    planted = [r["total_planted"] for r in results]
    harvested = [r["total_harvested"] for r in results]
    overflow = [r["shed_overflow_turns"] for r in results]
    revenue = [r["total_revenue_approx"] for r in results]

    print(f"\n{'='*70}")
    print(f"POLICY {policy} — AGGREGATE RESULTS ({len(results)} runs)")
    print(f"{'='*70}")
    print(f"  Average Reward:         ${statistics.mean(rewards):,.0f}")
    print(f"  Median Reward:          ${statistics.median(rewards):,.0f}")
    print(f"  Std Deviation:          ${statistics.stdev(rewards):,.0f}" if len(rewards) > 1 else "  Std Deviation:          N/A")
    print(f"  Best Reward:            ${max(rewards):,.0f}")
    print(f"  Worst Reward:           ${min(rewards):,.0f}")
    print(f"  Avg Melon Sell Price:   ${statistics.mean(prices):,.0f}")
    print(f"  Avg Shed Level:         {statistics.mean(shed_levels):.1f} items")
    print(f"  Avg Shed Overflow Turns:{statistics.mean(overflow):.1f}")
    print(f"  Avg Total Revenue:      ${statistics.mean(revenue):,.0f}")
    print(f"  Avg Melons Sold:        {statistics.mean(melons):.0f}")
    print(f"  Avg Tiles Planted:      {statistics.mean(planted):.0f}")
    print(f"  Avg Harvest Actions:    {statistics.mean(harvested):.0f}")
    print()

    # Production efficiency
    # Theoretical max: 100 tiles, 2 full melon cycles (Day 0-12, Day 12-24)
    # = 200 tile-cycles * 6 melons = 1,200 melons
    # Plus partial 3rd cycle on NW (Day 0 plant, Day 12 harvest, Day 12 replant, Day 24 harvest, Day 24 replant -> no time)
    # Actually: NW 25 tiles * 2 cycles = 300 melons, other 75 tiles * 1 cycle = 450 melons
    # But expansion happens Day 12-13, so other 75 tiles get 1 cycle max
    # Theoretical max with current expansion timing:
    #   NW 25 tiles: plant D0, harvest D12, replant D12, harvest D24 -> 2 cycles * 25 * 6 = 300 melons
    #   NE 25 tiles: available D12, plant ~D13, harvest ~D25 -> 1 cycle * 25 * 6 = 150 melons
    #   SW 25 tiles: available D12, plant ~D13, harvest ~D25 -> 1 cycle * 25 * 6 = 150 melons
    #   SE 25 tiles: available D13, plant ~D14, harvest ~D26 -> 1 cycle * 25 * 6 = 150 melons
    #   Total theoretical: 750 melons
    theoretical_max_melons = 750
    theoretical_max_revenue = theoretical_max_melons * 250  # at base price

    avg_melons = statistics.mean(melons)
    avg_rev = statistics.mean(revenue)

    print(f"  === PRODUCTION EFFICIENCY ===")
    print(f"  Theoretical Max Melon Production: {theoretical_max_melons} melons")
    print(f"  Actual Avg Melon Production:      {avg_melons:.0f} melons")
    print(f"  Production Efficiency:            {100*avg_melons/theoretical_max_melons:.1f}%")
    print()
    print(f"  Theoretical Max Harvests:         {theoretical_max_melons/6:.0f} harvest actions")
    print(f"  Actual Avg Harvests:              {statistics.mean(harvested):.0f}")
    print()
    print(f"  Max Possible Revenue (all @$250): ${theoretical_max_revenue:,}")
    print(f"  Actual Avg Revenue:               ${avg_rev:,.0f}")
    print(f"  Revenue Efficiency:               {100*avg_rev/theoretical_max_revenue:.1f}%")
    print(f"{'='*70}")


if __name__ == "__main__":
    print("=" * 70)
    print("A/B/C SELLING POLICY BENCHMARK")
    print("=" * 70)

    all_results = {}
    for policy in ["A", "B", "C"]:
        print(f"\n--- Running Policy {policy} (20 simulations) ---")
        results = run_benchmark(policy, n_runs=20)
        all_results[policy] = results

    for policy in ["A", "B", "C"]:
        report(policy, all_results[policy])

    # Final comparison table
    print("\n" + "=" * 70)
    print("COMPARISON TABLE")
    print("=" * 70)
    print(f"{'Metric':<30s} {'Policy A':>12s} {'Policy B':>12s} {'Policy C':>12s}")
    print("-" * 70)
    for metric, label in [
        ("reward", "Avg Reward"),
        ("melons_sold", "Avg Melons Sold"),
        ("avg_sell_price", "Avg Sell Price"),
        ("avg_shed_level", "Avg Shed Level"),
        ("shed_overflow_turns", "Shed Overflow Turns"),
        ("total_planted", "Avg Planted"),
        ("total_harvested", "Avg Harvested"),
    ]:
        vals = {}
        for p in ["A", "B", "C"]:
            vals[p] = statistics.mean([r[metric] for r in all_results[p]])
        if metric == "reward":
            print(f"  {label:<28s} ${vals['A']:>10,.0f} ${vals['B']:>10,.0f} ${vals['C']:>10,.0f}")
        elif "price" in metric:
            print(f"  {label:<28s} ${vals['A']:>10,.0f} ${vals['B']:>10,.0f} ${vals['C']:>10,.0f}")
        else:
            print(f"  {label:<28s} {vals['A']:>11.1f} {vals['B']:>11.1f} {vals['C']:>11.1f}")
    print("=" * 70)
