import sys, os, statistics, argparse
sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
from fieldops.agent import _coordinator_instance
from fieldops.core.strategy import StrategyConfig

ap = argparse.ArgumentParser(); ap.add_argument("--tc", type=int, default=20)
tc = ap.parse_args().tc

rs = []
for s in range(1, 21):
    env = make("kaggriculture", configuration={"seed": s}, debug=True)
    _coordinator_instance.strategy_config = StrategyConfig(target_crops=tc)
    steps = env.run(["src/fieldops/agent.py", "pass"])
    r = steps[-1][0].reward
    illegal = sum(1 for st in steps if st[0].status == "INVALID")
    if illegal:
        print(f"ILLEGAL seed {s}")
    rs.append(r)
print(f"TC={tc} mean={statistics.mean(rs):,.2f} med={statistics.median(rs):,.0f} min={min(rs):,.0f} max={max(rs):,.0f} std={statistics.stdev(rs):,.2f}")
