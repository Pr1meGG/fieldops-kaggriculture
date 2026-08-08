import multiprocessing
import pandas as pd
from kaggle_environments import make
import sys, os
sys.path.insert(0, os.path.abspath("src"))
from fieldops.agent import agent

def test_seed(seed):
    env = make("kaggriculture", debug=False, configuration={"episodeSteps": 721, "seed": seed})
    env.run([agent, "pass"])
    return env.steps[-1][0].reward or 0

if __name__ == "__main__":
    seeds = list(range(100))
    with multiprocessing.Pool() as p:
        results = p.map(test_seed, seeds)
    mean_val = sum(results) / len(results)
    print(f"Mean Reward over 100 seeds: {mean_val}")
