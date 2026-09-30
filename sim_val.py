import sys, os, statistics
sys.path.insert(0, os.path.abspath("src"))
from kaggle_environments import make
rs=[]
for s in range(1, 51):
    env = make("kaggriculture", configuration={"seed": s}, debug=True)
    steps = env.run(["src/fieldops/agent.py", "pass"])
    rs.append(steps[-1][0].reward)
print(f"N=50 mean={statistics.mean(rs):,.2f} med={statistics.median(rs):,.0f} min={min(rs):,.0f} max={max(rs):,.0f} std={statistics.stdev(rs):,.2f}")
