# FieldOps 🌾

> An autonomous farming agent for the [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture) Kaggle competition.

FieldOps is a **portfolio-quality** AI agent project. It is designed to be as readable and maintainable as it is competitive. Every decision is documented. Every module has a single responsibility.

---

## Competition Summary

Kaggriculture is a two-player, turn-based farming simulation. Each player manages a 10×10 farm over a 30-day season (720 turns). The player with the most coins at the end wins.

Key mechanics:
- **Crops**: Wheat, Carrot, Tomato, Strawberry, Melon — each with different cost, yield, and market dynamics
- **Animals**: Goose (eggs), Cow (milk), Sheep (wool) — require daily feeding with wheat
- **Market**: Dynamic pricing — oversupply crashes premium goods, scarcity boosts staples
- **Town**: Shops unlock over time, increasing product demand and sustaining market prices
- **Workers**: Hire farm hands for parallel action coverage; cost rises per hire per day

Full rules: [`competition/README.md`](competition/README.md)  
Agent guide: [`competition/AGENTS.md`](competition/AGENTS.md)

---

## Project Goals

1. **Win games** — compete effectively on the Kaggle leaderboard
2. **Stay readable** — any module should be understandable after 6 months of absence
3. **Stay modular** — features are isolated; replacing one strategy does not break another
4. **Document decisions** — see [`DECISIONS.md`](DECISIONS.md) for every architectural choice

---

## Repository Structure

```
fieldops/
├── README.md               # This file
├── BLUEPRINT.md            # Architecture overview and module responsibilities
├── ORCHESTRATION.md        # How the agent makes decisions each turn
├── ROADMAP.md              # Development phases and milestones
├── TASKS.md                # Active task list (sprint board)
├── CHANGELOG.md            # Record of meaningful changes
├── DECISIONS.md            # Architectural decision records (ADRs)
│
├── competition/            # Official competition docs (do not modify)
│   ├── README.md
│   └── AGENTS.md
│
├── docs/                   # Supplementary research and analysis
│
├── src/                    # Agent source code
│   └── fieldops/
│       ├── agent.py        # Entry point — the agent() function
│       ├── state.py        # Observation parsing and state representation
│       ├── planner.py      # High-level strategic planning
│       ├── executor.py     # Action selection and output formatting
│       └── constants.py    # Game constants (no magic numbers)
│
├── tests/                  # Test suite
│
├── submissions/            # Versioned submission archives
│
└── notebooks/              # Exploratory analysis and prototyping
```

---

## Quickstart

```bash
# 1. Activate the virtual environment
source .venv/bin/activate

# 2. Verify the environment loads
python tests/test.py

# 3. Run the agent against the built-in random opponent
python -c "
from kaggle_environments import make
from src.fieldops.agent import agent
env = make('kaggriculture', debug=True)
env.run([agent, 'random'])
final = env.steps[-1]
for i, s in enumerate(final):
    print(f'Player {i}: reward={s.reward}')
"
```

---

## Development Workflow

1. Check [`TASKS.md`](TASKS.md) to see what the current sprint is working on
2. Check [`DECISIONS.md`](DECISIONS.md) before making any architectural change
3. After completing a task, update `TASKS.md`, add a `CHANGELOG.md` entry, and commit

The [`ROADMAP.md`](ROADMAP.md) shows all planned phases and their definitions of done.

---

## Submitting

```bash
# Single-file submission
kaggle competitions submit kaggriculture -f submissions/main.py -m "message"

# Multi-file submission
kaggle competitions submit kaggriculture -f submissions/submission.tar.gz -m "message"
```

---

## Philosophy

> Build incrementally. Document decisions. Prefer clarity over cleverness.

This project follows ten principles documented in `BLUEPRINT.md`. The short version: every optimization needs a measurable reason, every module does one thing, and nothing is magic.
