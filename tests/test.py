from kaggle_environments import make

env = make("kaggriculture", debug=True)

print(env.name)
print("Environment loaded successfully!")