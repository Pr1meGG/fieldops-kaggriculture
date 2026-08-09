# Kaggriculture Kaggle Cloud CPU Research Workflow

To run heavy simulations and parameter sweeps off your local machine, we have established a robust, reproducible cloud pipeline using Kaggle Notebooks on CPU. 

**DO NOT** submit this notebook to the competition. It is strictly for executing experiments, extracting replays, and generating telemetry CSVs.

---

## 1. Setup the Kaggle Notebook

1. **Create Notebook:** In Kaggle, go to **Create > New Notebook**.
2. **Environment:** Keep the default Python environment (GPU is NOT needed; our engine is CPU-bound and using CPU prevents quota exhaustion).
3. **Upload Code:** You can either:
   - Import the `research/kaggle_research.ipynb` provided in this repository directly into Kaggle via **File > Import Notebook**.
   - Or just copy-paste the cells.
4. **Internet Access:** Ensure Internet is turned **ON** in the Notebook settings (so the notebook can `git clone` the repository and `pip install`).

---

## 2. Using the Notebook

The notebook is pre-configured with a 6-step pipeline:

### Step 1 & 2: Environment & Clone
It installs the correct `kaggle-environments==1.32.4` version and clones the repository.

### Step 3: Select Git Commit
**NEVER TEST AN UNTRACKED AGENT.**
In the notebook, set `TARGET_COMMIT = '1b05b9b'` to the specific commit you are benchmarking. The script will check it out. This ensures 100% reproducibility.

### Step 4 & 5: Run the Benchmark
The notebook uses `benchmark_runner.py`, a robust CLI tool we built for this exact purpose.

**How to run 3 Seeds (Validation):**
```bash
!python research/benchmark_runner.py \
    --agent src/fieldops/agent.py \
    --opponent pass \
    --seeds 1 2 3 \
    --experiment-name my_3seed_test \
    --results-dir /kaggle/working/results
```

**How to run 10 Seeds with Replays:**
```bash
!python research/benchmark_runner.py \
    --agent src/fieldops/agent.py \
    --opponent starter \
    --seeds 1 2 3 4 5 6 7 8 9 10 \
    --experiment-name seb_plus_plus_10seed \
    --save-replays \
    --results-dir /kaggle/working/results
```

**How to run 20 Seeds:**
```bash
!python research/benchmark_runner.py \
    --agent src/fieldops/agent.py \
    --opponent starter \
    --seeds $(seq 1 20 | tr '\n' ' ') \
    --experiment-name heavy_20seed_test \
    --save-replays \
    --results-dir /kaggle/working/results
```

### Step 6: Download Artifacts
The notebook compresses the results directory into `results.tar.gz`. You can download this directly from the Kaggle Data/Output panel on the right side of the screen.

---

## 3. Storage and Results

Inside `/kaggle/working/results/<experiment-name>/` you will find:
- `metadata.json`: The exact commit, engine version, python version, and command arguments.
- `summary.md`: A markdown summary of wins, margins, standard deviations, and max/min rewards.
- `results.csv`: 35+ metrics extracted per episode (reward, cash, peak workers, animal counts, crop revenue, weed actions, etc.).
- `telemetry/`: Raw JSON metrics per seed.
- `replays/`: (If `--save-replays` was used) Full `.json` game replays identical to leaderboard format, which you can drop into the Kaggle visualizer.

---

## 4. Performance & Runtime

**Observed metrics on Kaggle CPU infrastructure:**
- **Time per 721-step episode:** ~20 seconds
- **Memory footprint:** ~28-30 MB Peak
- **Kaggle Session Capacity:** A single 9-hour Kaggle session can comfortably fit **~1,500 sequential episodes**.
- A standard 20-seed benchmark against 5 different opponents takes roughly **35 minutes** to run sequentially.

Multiprocessing is NOT strictly required given this high throughput, ensuring stability and deterministic execution.

---

## 5. Workflow Principles

- **LOCAL PC**: Code authoring, light debugging, replay analysis (reading the JSONs downloaded from Kaggle).
- **KAGGLE CLOUD CPU**: Heavy simulation (20-seed benchmarks, matrix testing).
- **KAGGLE COMPETITION**: ONLY used when the agent is fully validated and ready for the leaderboard.

Never overwrite `kaggriculture-submission-5pm` or similar release tags. Create dedicated research branches and pull the specific commit into the Kaggle Notebook.
