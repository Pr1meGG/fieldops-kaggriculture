import sys
from kaggle_environments import make
env = make("kaggriculture", configuration={"episodeSteps": 10})
print("Available actions in Kaggriculture schema:")
# Actually we can just look at the observation schema or just run a quick test.
