#!/usr/bin/env python3
"""
benchmark_runner.py — Reusable Kaggriculture Research Benchmark Runner
=======================================================================

Usage:
    python research/benchmark_runner.py \
        --agent src/fieldops/agent.py \
        --opponent pass \
        --seeds 1 2 3 \
        --experiment-name champion_validation \
        --save-replays

Output structure:
    results/<experiment-name>/
        metadata.json
        results.csv
        summary.md
        replays/
            seed_<N>.json
        telemetry/
            seed_<N>.json
"""

import sys
import os
import argparse
import csv
import json
import time
import datetime
import subprocess
import tracemalloc

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)

from kaggle_environments import make

# ─────────────────────────────────────────────────────────────────────────────
# Git / version helpers
# ─────────────────────────────────────────────────────────────────────────────

def _git(cmd: str, cwd: str = _PROJECT_ROOT) -> str:
    try:
        return subprocess.check_output(
            ["git"] + cmd.split(), cwd=cwd, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return ""

def get_commit_hash() -> str:
    return _git("rev-parse HEAD") or "UNKNOWN"

def get_branch() -> str:
    return _git("rev-parse --abbrev-ref HEAD") or "UNKNOWN"

def get_engine_version() -> str:
    try:
        import kaggle_environments
        return kaggle_environments.__version__
    except Exception:
        return "UNKNOWN"

def get_python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


# ─────────────────────────────────────────────────────────────────────────────
# Metrics extraction
# ─────────────────────────────────────────────────────────────────────────────

MOVEMENT_CMDS = {"NORTH", "SOUTH", "EAST", "WEST"}
PRODUCTIVE_CMDS = {"WATER", "HARVEST", "PLANT", "CARE", "FEED", "FERTILIZE",
                   "DIG", "COLLECT", "DROP", "PICKUP", "BUILD_PASTURE", "PLACE"}


def extract_metrics(steps: list, player_idx: int = 0) -> dict:
    opp_idx = 1 - player_idx

    hires_total = 0
    movement_actions = 0
    productive_actions = 0
    weed_actions = 0
    animal_feed = 0
    animal_care = 0
    animal_escapes = 0

    sells = {}
    sell_revenue = {}
    unlocked_quads = set()
    peak_hands = 0
    hand_counts = []
    weed_counts = {}

    for step_data in steps:
        if player_idx >= len(step_data):
            continue
        agent_step = step_data[player_idx]
        obs = agent_step.observation
        if not isinstance(obs, dict) or obs.get("step") is None:
            continue

        day = obs.get("day", 0)
        hour = obs.get("hour", 0)
        farms = obs.get("farms", [])
        if player_idx >= len(farms):
            continue

        my_farm = farms[player_idx]
        hands = my_farm.get("hands", [])
        n_hands = len(hands)
        peak_hands = max(peak_hands, n_hands)
        hand_counts.append(n_hands)

        if hour == 0:
            tiles = my_farm.get("tiles", [])
            weeds = sum(
                1 for row in tiles for t in row
                if isinstance(t, dict) and t.get("kind") == "WEED"
            )
            weed_counts[day] = weeds

        unlocked_quads.update(my_farm.get("unlocked_quadrants", []))

        market = obs.get("market", {})
        prices = market.get("prices", {})

        action = agent_step.action
        if not action:
            continue

        for mkt_act in action.get("market", []):
            if not mkt_act:
                continue
            cmd = mkt_act[0]
            if cmd == "HIRE":
                hires_total += 1
            elif cmd == "SELL" and len(mkt_act) >= 3:
                item, qty = mkt_act[1], mkt_act[2]
                price = prices.get(item, 0)
                sells[item] = sells.get(item, 0) + qty
                sell_revenue[item] = sell_revenue.get(item, 0) + qty * price

        all_ua = []
        fa = action.get("farmer")
        if fa:
            all_ua.append(fa)
        all_ua.extend(action.get("hands", []))

        for ua in all_ua:
            if not ua:
                continue
            cmd = ua[0] if isinstance(ua, list) else ua
            if cmd in MOVEMENT_CMDS:
                movement_actions += 1
            elif cmd in PRODUCTIVE_CMDS:
                productive_actions += 1
                if cmd == "DIG":
                    weed_actions += 1
                elif cmd == "FEED":
                    animal_feed += 1
                elif cmd == "CARE":
                    animal_care += 1

    # Final state
    final_reward = 0.0
    final_money = 0.0
    opp_final_reward = 0.0
    if steps:
        final_step = steps[-1]
        if player_idx < len(final_step):
            final_reward = final_step[player_idx].reward or 0.0
            fobs = final_step[player_idx].observation
            if isinstance(fobs, dict) and "farms" in fobs:
                final_money = fobs["farms"][player_idx].get("money", 0)
        if opp_idx < len(final_step):
            opp_final_reward = final_step[opp_idx].reward or 0.0

    # Livestock from last observation that has animals
    sheep_count = cow_count = goose_count = 0
    for step_data in reversed(steps):
        if player_idx >= len(step_data):
            continue
        obs = step_data[player_idx].observation
        if not isinstance(obs, dict):
            continue
        farms = obs.get("farms", [])
        if player_idx >= len(farms):
            continue
        tiles = farms[player_idx].get("tiles", [])
        for row in tiles:
            for t in row:
                if isinstance(t, dict):
                    a = t.get("animal")
                    if a == "SHEEP":
                        sheep_count += 1
                    elif a == "COW":
                        cow_count += 1
                    elif a == "GOOSE":
                        goose_count += 1
        if sheep_count + cow_count + goose_count > 0:
            break

    crop_items = {"WHEAT", "MELON", "CARROT", "STRAWBERRY", "TOMATO"}
    livestock_items = {"MILK", "WOOL", "EGG", "FERTILIZER"}
    crop_revenue = sum(sell_revenue.get(i, 0) for i in crop_items)
    livestock_revenue = sum(sell_revenue.get(i, 0) for i in livestock_items)
    total_sell_revenue = sum(sell_revenue.values())

    total_unit_actions = movement_actions + productive_actions
    worker_utilization = (
        productive_actions / total_unit_actions * 100.0
        if total_unit_actions > 0 else 0.0
    )
    avg_hands = sum(hand_counts) / len(hand_counts) if hand_counts else 0.0

    return {
        "final_reward": round(final_reward, 2),
        "final_cash": round(final_money, 2),
        "opp_final_reward": round(opp_final_reward, 2),
        "result": "WIN" if final_reward > opp_final_reward else "LOSS",
        "margin": round(final_reward - opp_final_reward, 2),
        "workers_peak": peak_hands,
        "workers_average": round(avg_hands, 2),
        "workers_total_hires": hires_total,
        "land_quadrants": len(unlocked_quads),
        "sheep": sheep_count,
        "cows": cow_count,
        "goose": goose_count,
        "livestock": sheep_count + cow_count + goose_count,
        "melon_sold": sells.get("MELON", 0),
        "strawberry_sold": sells.get("STRAWBERRY", 0),
        "wheat_sold": sells.get("WHEAT", 0),
        "milk_sold": sells.get("MILK", 0),
        "wool_sold": sells.get("WOOL", 0),
        "fertilizer_sold": sells.get("FERTILIZER", 0),
        "melon_revenue": round(sell_revenue.get("MELON", 0), 2),
        "straw_revenue": round(sell_revenue.get("STRAWBERRY", 0), 2),
        "wheat_revenue": round(sell_revenue.get("WHEAT", 0), 2),
        "milk_revenue": round(sell_revenue.get("MILK", 0), 2),
        "wool_revenue": round(sell_revenue.get("WOOL", 0), 2),
        "fert_revenue": round(sell_revenue.get("FERTILIZER", 0), 2),
        "crop_revenue": round(crop_revenue, 2),
        "livestock_revenue": round(livestock_revenue, 2),
        "market_revenue": round(total_sell_revenue, 2),
        "movement_actions": movement_actions,
        "productive_actions": productive_actions,
        "worker_utilization_pct": round(worker_utilization, 2),
        "weed_actions": weed_actions,
        "animal_feed": animal_feed,
        "animal_care": animal_care,
        "animal_escapes": animal_escapes,
        "weed_at_d23": weed_counts.get(23, 0),
        "weed_peak": max(weed_counts.values()) if weed_counts else 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Replay serialiser
# ─────────────────────────────────────────────────────────────────────────────

def _step_to_dict(step):
    result = []
    for agent_step in step:
        obs = agent_step.observation
        if not isinstance(obs, dict):
            obs = dict(obs) if hasattr(obs, '__iter__') else {}
        result.append({
            "observation": obs,
            "action": agent_step.action,
            "reward": agent_step.reward,
            "status": agent_step.status,
        })
    return result


def save_replay_json(steps: list, path: str, info: dict) -> None:
    payload = {
        "info": info,
        "steps": [_step_to_dict(s) for s in steps],
        "rewards": [steps[-1][i].reward for i in range(len(steps[-1]))],
        "statuses": [steps[-1][i].status for i in range(len(steps[-1]))],
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# Single episode runner
# ─────────────────────────────────────────────────────────────────────────────

def run_episode(agent_path: str, opponent: str, seed: int, save_replay: bool = False) -> dict:
    tracemalloc.start()
    t_start = time.monotonic()

    env = make("kaggriculture", debug=False, configuration={"seed": seed})
    steps = env.run([agent_path, opponent])

    elapsed = time.monotonic() - t_start
    curr_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    metrics = extract_metrics(steps, player_idx=0)
    metrics["seed"] = seed
    metrics["elapsed_seconds"] = round(elapsed, 2)
    metrics["peak_memory_mb"] = round(peak_mem / 1024 / 1024, 2)
    metrics["n_steps"] = len(steps)

    print(
        f"  seed={seed:>5}  reward={metrics['final_reward']:>10,.2f}"
        f"  opp={metrics['opp_final_reward']:>10,.2f}"
        f"  {metrics['result']:<4}"
        f"  margin={metrics['margin']:>+10,.2f}"
        f"  hands={metrics['workers_peak']}"
        f"  time={elapsed:.1f}s"
    )

    if save_replay:
        metrics["_steps"] = steps

    return metrics


# ─────────────────────────────────────────────────────────────────────────────
# Full experiment runner
# ─────────────────────────────────────────────────────────────────────────────

def run_experiment(
    agent_obj,
    agent_name: str,
    opponent: str,
    seeds: list,
    experiment_name: str,
    champion_commit: str = "UNKNOWN",
    save_replays: bool = False,
    results_dir: str = None,
) -> str:
    commit = get_commit_hash()
    branch = get_branch()
    engine_ver = get_engine_version()
    py_ver = get_python_version()
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    if results_dir is None:
        results_dir = os.path.join(_PROJECT_ROOT, "research", "results")

    out_dir = os.path.join(results_dir, experiment_name)
    replay_dir = os.path.join(out_dir, "replays")
    telemetry_dir = os.path.join(out_dir, "telemetry")
    os.makedirs(out_dir, exist_ok=True)
    if save_replays:
        os.makedirs(replay_dir, exist_ok=True)
    os.makedirs(telemetry_dir, exist_ok=True)

    print("=" * 72)
    print(f"EXPERIMENT:      {experiment_name}")
    print(f"RUNNER COMMIT:   {commit}")
    print(f"CHAMPION COMMIT: {champion_commit}")
    print(f"BRANCH:          {branch}")
    print(f"ENGINE VERSION:  {engine_ver}")
    print(f"PYTHON VERSION:  {py_ver}")
    print(f"AGENT:           {agent_name}")
    print(f"OPPONENT:        {opponent}")
    print(f"SEEDS:           {seeds}")
    print(f"TIMESTAMP:       {ts}")
    print("=" * 72)

    metadata = {
        "experiment_name": experiment_name,
        "runner_commit": commit,
        "champion_commit": champion_commit,
        "branch": branch,
        "engine_version": engine_ver,
        "python_version": py_ver,
        "timestamp": ts,
        "agent": agent_name,
        "opponent": opponent,
        "seed_list": seeds,
        "save_replays": save_replays,
    }
    with open(os.path.join(out_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    all_results = []
    csv_fields = None

    for seed in seeds:
        result = run_episode(agent_obj, opponent, seed, save_replay=save_replays)

        if save_replays and "_steps" in result:
            replay_meta = {"runner_commit": commit, "champion_commit": champion_commit, "seed": seed,
                           "agent": agent_name, "opponent": opponent}
            replay_path = os.path.join(replay_dir, f"seed_{seed:05d}.json")
            save_replay_json(result.pop("_steps"), replay_path, replay_meta)
            result["replay_path"] = replay_path
        else:
            result.pop("_steps", None)
            result["replay_path"] = ""

        with open(os.path.join(telemetry_dir, f"seed_{seed:05d}.json"), "w") as f:
            json.dump(result, f, indent=2, default=str)

        all_results.append(result)
        if csv_fields is None:
            csv_fields = [k for k in result.keys() if not k.startswith("_")]

    csv_path = os.path.join(out_dir, "results.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_results)

    rewards = [r["final_reward"] for r in all_results]
    opps = [r["opp_final_reward"] for r in all_results]
    margins = [r["margin"] for r in all_results]
    wins = sum(1 for r in all_results if r["result"] == "WIN")
    times = [r["elapsed_seconds"] for r in all_results]

    import statistics as stats

    def _fmt_std(data):
        return f"${stats.stdev(data):,.2f}" if len(data) > 1 else "N/A"

    summary = [
        f"# Experiment: {experiment_name}",
        "",
        f"**Timestamp**: {ts}",
        f"**Runner Commit**: `{commit}`",
        f"**Champion Commit**: `{champion_commit}`",
        f"**Branch**: `{branch}`",
        f"**Engine**: `kaggle-environments {engine_ver}`",
        f"**Python**: `{py_ver}`",
        f"**Agent**: `{agent_name}`",
        f"**Opponent**: `{opponent}`",
        f"**Seeds**: {seeds}",
        "",
        "## Results",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Episodes | {len(seeds)} |",
        f"| Wins | {wins}/{len(seeds)} ({100*wins//len(seeds)}%) |",
        f"| Mean reward | ${stats.mean(rewards):,.2f} |",
        f"| Std reward | {_fmt_std(rewards)} |",
        f"| Min reward | ${min(rewards):,.2f} |",
        f"| Max reward | ${max(rewards):,.2f} |",
        f"| Mean margin | ${stats.mean(margins):+,.2f} |",
        f"| Mean opp | ${stats.mean(opps):,.2f} |",
        f"| Avg time/ep | {stats.mean(times):.1f}s |",
        f"| Total time | {sum(times):.0f}s ({sum(times)/60:.1f}min) |",
        "",
        "## Per-Seed Results",
        "",
        "| Seed | Reward | Opp | Result | Margin | Time |",
        "|------|--------|-----|--------|--------|------|",
    ]
    for r in all_results:
        summary.append(
            f"| {r['seed']} | ${r['final_reward']:,.0f} | ${r['opp_final_reward']:,.0f}"
            f" | {r['result']} | ${r['margin']:+,.0f} | {r['elapsed_seconds']:.1f}s |"
        )
    summary += [
        "",
        "## Files",
        f"- `results.csv`: {len(all_results)} rows, {len(csv_fields)} columns",
        f"- `replays/`: {'SAVED' if save_replays else 'NOT SAVED'}",
        f"- `telemetry/`: {len(all_results)} per-seed JSON files",
        f"- `metadata.json`: experiment configuration",
    ]

    with open(os.path.join(out_dir, "summary.md"), "w") as f:
        f.write("\n".join(summary))

    print()
    print("=" * 72)
    print(f"RESULTS SUMMARY  {experiment_name}")
    print(f"  Wins:        {wins}/{len(seeds)}")
    print(f"  Mean reward: ${stats.mean(rewards):,.2f}")
    print(f"  Range:       ${min(rewards):,.2f} — ${max(rewards):,.2f}")
    print(f"  Mean margin: ${stats.mean(margins):+,.2f}")
    print(f"  Total time:  {sum(times):.0f}s ({sum(times)/60:.1f}min)")
    print(f"  Output dir:  {out_dir}")
    print("=" * 72)

    return out_dir


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Kaggriculture Research Benchmark Runner")
    parser.add_argument("--agent-root", default=None,
                        help="Optional isolated source directory to insert at sys.path[0]")
    parser.add_argument("--agent", default="src/fieldops/agent.py",
                        help="Agent path, built-in name, or module syntax (e.g. fieldops.agent:agent)")
    parser.add_argument("--champion-commit", default="UNKNOWN",
                        help="The exact git commit hash of the champion being evaluated")
    parser.add_argument("--opponent", default="pass",
                        help="Opponent path or built-in ('pass','random','starter'). Default: pass")
    parser.add_argument("--seeds", nargs="+", type=int, required=True,
                        help="Seed list, e.g. --seeds 1 2 3")
    parser.add_argument("--experiment-name", required=True,
                        help="Short name for output directory")
    parser.add_argument("--save-replays", action="store_true",
                        help="Save full replay JSON per episode")
    parser.add_argument("--results-dir", default=None,
                        help="Override output base directory (default: research/results/)")
    args = parser.parse_args()

    project_src = os.path.abspath(os.path.join(_PROJECT_ROOT, "src"))

    if args.agent_root:
        iso_root = os.path.abspath(args.agent_root)
        
        # 1. Remove project_src and the runner's own directory from sys.path
        sys.path = [p for p in sys.path if not os.path.abspath(p).startswith(os.path.abspath(_PROJECT_ROOT))]
        
        # 2. Remove any pre-loaded fieldops modules (e.g. from previous steps or auto-imports)
        keys_to_remove = [k for k in sys.modules.keys() if k == "fieldops" or k.startswith("fieldops.")]
        for k in keys_to_remove:
            del sys.modules[k]
            
        # 3. Insert the isolated root at the highest priority
        sys.path.insert(0, iso_root)
        
        print(f"[PRE-FLIGHT] Scrubbed project paths from sys.path")
        print(f"[PRE-FLIGHT] Scrubbed {len(keys_to_remove)} fieldops modules from sys.modules")
        print(f"[PRE-FLIGHT] Inserted isolated root: {iso_root}")
        print(f"[PRE-FLIGHT] Current sys.path[:3]: {sys.path[:3]}")
    else:
        sys.path.insert(0, project_src)

    agent_obj = args.agent
    agent_name = args.agent

    if ":" in args.agent:
        mod_name, func_name = args.agent.split(":")
        
        # 4. Import the requested agent ONLY AFTER isolation setup
        import importlib
        mod = importlib.import_module(mod_name)
        agent_obj = getattr(mod, func_name)
        
        agent_file = os.path.abspath(mod.__file__)
        
        print(f"\n{'='*72}")
        print(f"HARD VERIFICATION: AGENT ISOLATION")
        print(f"{'='*72}")
        print(f"Champion Commit:   {args.champion_commit}")
        print(f"Current Runner:    {get_commit_hash()}")
        print(f"Target Agent Mod:  {mod_name}")
        print(f"Loaded Agent Path: {agent_file}")
        
        if args.agent_root:
            iso_root = os.path.abspath(args.agent_root)
            
            # 5. Hard fail assertions
            if not agent_file.startswith(iso_root):
                raise AssertionError(f"FATAL: Agent loaded from {agent_file}, expected under {iso_root}")
            if agent_file.startswith(project_src):
                raise AssertionError(f"FATAL: Agent loaded from {agent_file}, which is in current repo src! Isolation failed.")
                
            print("Status:            PASS (Agent is fully isolated)")
        else:
            print("Status:            WARNING (No agent-root provided. Running from local checkout.)")
        print(f"{'='*72}\n")
    else:
        # Fallback for paths
        if not os.path.isabs(agent_obj) and os.path.exists(os.path.join(_PROJECT_ROOT, agent_obj)):
            agent_obj = os.path.join(_PROJECT_ROOT, agent_obj)

    opponent = args.opponent
    if not os.path.isabs(opponent) and os.path.exists(os.path.join(_PROJECT_ROOT, opponent)):
        opponent = os.path.join(_PROJECT_ROOT, opponent)

    run_experiment(
        agent_obj=agent_obj,
        agent_name=agent_name,
        opponent=opponent,
        seeds=args.seeds,
        experiment_name=args.experiment_name,
        champion_commit=args.champion_commit,
        save_replays=args.save_replays,
        results_dir=args.results_dir,
    )


if __name__ == "__main__":
    main()
