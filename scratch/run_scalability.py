"""
Experiment J1 + J2 — Logistics Scalability Study
=================================================
Isolated research script. Does NOT modify any production file.

J1: Fix production at 12 Melons, vary worker count (1,2,3,4,6,8,10)
    with the V1 (Hybrid) scheduler. Measure the scalability curve and
    find the worker count where marginal productivity becomes negative.

J2: For the same worker counts compare V1 vs V2 vs Hybrid schedulers.
"""

import os
import sys
import statistics
import json

sys.path.insert(0, os.path.abspath("src"))

from kaggle_environments import make
from fieldops.state import ObservationParser
from fieldops.managers.worker_manager import (
    HybridWorkerManager,
    V2WorkerManager,
)
from fieldops.managers.economy_manager import EconomyManager
from fieldops.managers.expansion_manager import ExpansionManager
from fieldops.managers.crop_manager import CropManager
from fieldops.managers.livestock_manager import LivestockManager
from fieldops.managers.market_manager import MarketManager
from fieldops.core.planner import DecisionContext
from fieldops.core.economy import EconomicModel
from fieldops.observatory.recorder import ObservatoryRecorder

SEEDS = [42, 43, 44, 45, 46]
TARGET_MELONS = 12
TARGET_LAND = 2  # starting land (unchanged)


# ---------------------------------------------------------------------------
# Lightweight stand-alone agent with configurable scheduler + fixed workers
# ---------------------------------------------------------------------------

class ScalabilityCoordinator:
    def __init__(self, scheduler_cls, fixed_workers: int):
        self.scheduler = scheduler_cls()
        self.fixed_workers = fixed_workers
        self.managers = [
            EconomyManager(),
            ExpansionManager(),
            self.scheduler,
            CropManager(),
            LivestockManager(),
            MarketManager(),
        ]
        self.obs_recorder = ObservatoryRecorder()
        self.last_snapshot = None

    def __call__(self, obs):
        state = ObservationParser.parse(obs)
        snapshot = EconomicModel.calculate(state, self.last_snapshot)
        self.last_snapshot = snapshot

        context = DecisionContext()
        context.economic_snapshot = snapshot

        for m in self.managers:
            m.initialize(context)
        for m in self.managers:
            m.update(state, context)
        for m in self.managers:
            m.plan(state, context)

        actions = {
            "farmer": ["PASS"],
            "hands": [["PASS"] for _ in range(len(state.my_farm.hands))],
            "market": [],
        }

        for m in self.managers:
            r = m.execute(state, context)
            if r.get("farmer"):
                actions["farmer"] = r["farmer"]
            if r.get("hands"):
                for i, ha in enumerate(r["hands"]):
                    if i < len(actions["hands"]):
                        actions["hands"][i] = ha
            if r.get("market"):
                actions["market"].extend(r["market"])

        step = obs.get("step", 0)
        my_farm = state.my_farm

        # Hire up to fixed_workers on step 0
        current_workers = len(my_farm.hands)
        needed = self.fixed_workers - current_workers
        if step == 0 and needed > 0:
            for _ in range(needed):
                actions["market"].append(["HIRE"])

        # Buy seeds to maintain TARGET_MELONS
        current_plants = sum(
            1 for row in my_farm.tiles for t in row if t.is_plant()
        )
        seeds_held = my_farm.seeds.get("MELON", 0) if my_farm.seeds else 0
        need_seeds = TARGET_MELONS - seeds_held - current_plants
        if need_seeds > 0 and my_farm.money >= need_seeds * 10:
            actions["market"].append(["BUY_SEED", "MELON", need_seeds])

        # Sell everything non-fertilizer
        if my_farm.shed:
            for item, count in my_farm.shed.items.items():
                if count > 0 and item != "FERTILIZER":
                    actions["market"].append(["SELL", item, count])

        return actions


# ---------------------------------------------------------------------------
# Action-level counters
# ---------------------------------------------------------------------------

PRODUCTIVE_CMDS = {"WATER", "HARVEST", "PLANT", "DROP", "DIG"}
MOVE_CMDS = {"NORTH", "SOUTH", "EAST", "WEST"}


def count_actions(action: dict):
    productive = 0
    movement = 0
    passes = 0
    all_unit_actions = [action.get("farmer", ["PASS"])] + action.get("hands", [])
    for ua in all_unit_actions:
        if not ua:
            passes += 1
            continue
        cmd = ua[0]
        if cmd in PRODUCTIVE_CMDS:
            productive += 1
        elif cmd in MOVE_CMDS:
            movement += 1
        else:
            passes += 1
    return productive, movement, passes


# ---------------------------------------------------------------------------
# Single episode runner
# ---------------------------------------------------------------------------

def run_episode(scheduler_cls, fixed_workers: int, seed: int):
    env = make(
        "kaggriculture",
        debug=False,
        configuration={"episodeSteps": 721, "seed": seed},
    )
    trainer = env.train([None, "random"])
    agent = ScalabilityCoordinator(scheduler_cls, fixed_workers)

    obs = trainer.reset()
    max_cash = float("-inf")
    min_cash = float("inf")
    total_productive = 0
    total_movement = 0
    total_pass = 0
    total_steps = 0

    while not env.done:
        try:
            action = agent(obs)
        except ValueError as e:
            if "out of range" in str(e):
                break
            raise

        p, m, ps = count_actions(action)
        total_productive += p
        total_movement += m
        total_pass += ps
        total_steps += 1

        obs, reward, done, info = trainer.step(action)

        farm = obs["farms"][0] if isinstance(obs, dict) else obs.farms[0]
        cash = farm.get("money", 0) if isinstance(farm, dict) else farm.money
        max_cash = max(max_cash, cash)
        min_cash = min(min_cash, cash)

    farm = obs["farms"][0] if isinstance(obs, dict) else obs.farms[0]
    final_cash = farm.get("money", 0) if isinstance(farm, dict) else farm.money

    return {
        "final_cash": final_cash,
        "max_cash": max_cash,
        "min_cash": min_cash,
        "productive": total_productive,
        "movement": total_movement,
        "passes": total_pass,
        "steps": total_steps,
    }


# ---------------------------------------------------------------------------
# Multi-seed evaluator
# ---------------------------------------------------------------------------

def evaluate(scheduler_cls, scheduler_name: str, fixed_workers: int, seeds):
    results = [run_episode(scheduler_cls, fixed_workers, s) for s in seeds]
    rewards = [r["final_cash"] for r in results]
    unit_count = fixed_workers + 1  # workers + farmer

    mean_r = statistics.mean(rewards)
    mean_prod = statistics.mean(r["productive"] for r in results)
    mean_move = statistics.mean(r["movement"] for r in results)
    mean_pass = statistics.mean(r["passes"] for r in results)
    mean_steps = statistics.mean(r["steps"] for r in results)
    total_actions = mean_prod + mean_move + mean_pass
    move_pct = 100 * mean_move / total_actions if total_actions > 0 else 0
    prod_per_worker = mean_prod / unit_count
    revenue_per_worker = mean_r / unit_count

    return {
        "scheduler": scheduler_name,
        "workers": fixed_workers,
        "units": unit_count,
        "mean_reward": mean_r,
        "median_reward": statistics.median(rewards),
        "min_reward": min(rewards),
        "max_reward": max(rewards),
        "rewards": rewards,
        "productive": mean_prod,
        "movement": mean_move,
        "passes": mean_pass,
        "movement_pct": move_pct,
        "prod_per_worker": prod_per_worker,
        "revenue_per_worker": revenue_per_worker,
        "max_cash": statistics.mean(r["max_cash"] for r in results),
        "min_cash": statistics.mean(r["min_cash"] for r in results),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    worker_counts = [1, 2, 3, 4, 6, 8, 10]

    schedulers = [
        (HybridWorkerManager, "V1_Hybrid"),
        (V2WorkerManager, "V2_TileCentric"),
    ]

    all_results = []

    # J1: V1 only — scalability curve
    print("=" * 60)
    print("J1 — V1 Scheduler Scalability Curve")
    print("=" * 60)
    j1_results = []
    for w in worker_counts:
        print(f"  V1 / {w} workers ...", end=" ", flush=True)
        r = evaluate(HybridWorkerManager, "V1_Hybrid", w, SEEDS)
        j1_results.append(r)
        all_results.append(r)
        print(f"${r['mean_reward']:.0f}")

    # J2: scheduler comparison at each worker count
    print()
    print("=" * 60)
    print("J2 — Scheduler Comparison")
    print("=" * 60)
    for sched_cls, sched_name in schedulers[1:]:  # skip V1 already done
        for w in worker_counts:
            print(f"  {sched_name} / {w} workers ...", end=" ", flush=True)
            r = evaluate(sched_cls, sched_name, w, SEEDS)
            all_results.append(r)
            print(f"${r['mean_reward']:.0f}")

    # -----------------------------------------------------------------------
    # Build report
    # -----------------------------------------------------------------------
    lines = []
    lines.append("# Experiment J1+J2 — Logistics Scalability Report\n")
    lines.append("## J1: V1 (Hybrid) Scalability Curve — Fixed 12 Melons\n")
    lines.append("| Workers | Mean $  | Δ vs 2w | Prod/Worker | Move% | Revenue/Worker |")
    lines.append("|---------|---------|---------|-------------|-------|----------------|")

    baseline_2w = next(r for r in j1_results if r["workers"] == 2)["mean_reward"]
    prev_reward = None
    for r in j1_results:
        delta_2w = r["mean_reward"] - baseline_2w
        marginal = (
            f"+${r['mean_reward'] - prev_reward:.0f}"
            if prev_reward is not None
            else "—"
        )
        lines.append(
            f"| {r['workers']} | ${r['mean_reward']:.0f} | {delta_2w:+.0f} | "
            f"{r['prod_per_worker']:.1f} | {r['movement_pct']:.1f}% | "
            f"${r['revenue_per_worker']:.0f} |"
        )
        prev_reward = r["mean_reward"]

    lines.append("")
    lines.append("## J2: Scheduler Comparison\n")

    # Build scheduler × worker matrix
    sched_names = ["V1_Hybrid", "V2_TileCentric"]
    header = "| Workers | " + " | ".join(sched_names) + " |"
    sep = "|---------|" + "|".join(["-------"] * len(sched_names)) + "|"
    lines.append(header)
    lines.append(sep)

    by_sched_worker = {}
    for r in all_results:
        by_sched_worker[(r["scheduler"], r["workers"])] = r["mean_reward"]

    for w in worker_counts:
        row = f"| {w} | "
        row += " | ".join(
            f"${by_sched_worker.get((s, w), 0):.0f}" for s in sched_names
        )
        row += " |"
        lines.append(row)

    lines.append("")
    lines.append("## Key Observations\n")

    # find peak V1
    peak_v1 = max(j1_results, key=lambda r: r["mean_reward"])
    first_negative = None
    for i in range(1, len(j1_results)):
        if j1_results[i]["mean_reward"] < j1_results[i - 1]["mean_reward"]:
            first_negative = j1_results[i]["workers"]
            break

    lines.append(f"* **Peak V1 reward:** ${peak_v1['mean_reward']:.0f} at {peak_v1['workers']} workers")
    if first_negative:
        lines.append(f"* **First negative marginal worker count (V1):** {first_negative} workers")
    else:
        lines.append("* V1 reward continues to increase or holds flat across all tested worker counts")
    lines.append(f"* **Control (2w V1):** ${baseline_2w:.0f}")

    # Scheduler winner at each worker count
    lines.append("\n### Scheduler winner at each worker count:")
    for w in worker_counts:
        scores = {s: by_sched_worker.get((s, w), 0) for s in sched_names}
        winner = max(scores, key=scores.get)
        lines.append(f"  * {w} workers → **{winner}** (${scores[winner]:.0f})")

    report = "\n".join(lines)

    with open("logistics_scalability_report.md", "w") as f:
        f.write(report)

    with open("logistics_scalability_data.json", "w") as f:
        json.dump(all_results, f, indent=2)

    print("\nResults saved to logistics_scalability_report.md")
    print(report)


if __name__ == "__main__":
    main()
