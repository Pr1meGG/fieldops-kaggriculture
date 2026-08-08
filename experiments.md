# Operations Research Experiment Registry

A chronological record of all rigorously validated economic hypotheses.

## Cumulative Statistics
### Algorithms
- **Experiments**: 1
- **Promoted**: 0
- **Average EV**: +$0

### Analysiss
- **Experiments**: 1
- **Promoted**: 0
- **Average EV**: +$0

### Bug Fixs
- **Experiments**: 1
- **Promoted**: 1
- **Average EV**: +$1004

### Parameters
- **Experiments**: 1
- **Promoted**: 1
- **Average EV**: +$5060

### Policys
- **Experiments**: 2
- **Promoted**: 0
- **Average EV**: +$0

### Submissions
- **Experiments**: 1
- **Promoted**: 0
- **Average EV**: +$0

---

## SUB-V3 [Submission] - Kaggle Submission
**Date**: 2026-08-08 07:53:24 | **Champion**: champion-seed-fix-v3 | **Decision**: SUBMITTED

### Benchmark Details
- **Parameter Values Tested**: Submission Archive Size: 13079 bytes
- **Sample Size**: 0 (Seeds: N/A)
- **Mean Reward**: $46925.00
- **Win Rate**: 0.00%

### Economic Attribution
Submission ID: 89341257. Archive packaged and verified successfully in clean isolated environment.

### Repository State
- **Branch**: main
- **Commit**: `2c918bb`
- **Tag**: `champion-seed-fix-v3`

---

## EXP-006 [Analysis] - Task Utility Determinants
**Date**: 2026-08-07 | **Champion**: champion-seed-fix-v3 | **Decision**: Hypothesis Generated

### Benchmark Details
- **Parameter Values Tested**: Random Forest Feature Importance
- **Sample Size**: 20 (Seeds: Random 800-819)
- **Mean Reward**: $0.00
- **Win Rate**: 0.00%

### Economic Attribution
Expected Harvest Value (38.9%) and Task Delay (22.5%) are the primary predictors of final monetary contribution. Travel distance accounted for only 6.4%, explaining why Hungarian assignment failed. Planting tasks uniquely carry 12.5% weight due to structural risk. The result generated the utility feature vectors for EXP-007.

### Repository State
- **Branch**: feature/utility-discovery
- **Commit**: `N/A`
- **Tag**: `N/A`

---

## EXP-005 [Algorithm] - Worker Assignment Logic
**Date**: 2026-08-07 | **Champion**: champion-seed-fix-v3 | **Decision**: REJECT

### Benchmark Details
- **Parameter Values Tested**: Greedy vs Hungarian
- **Sample Size**: 100 (Seeds: Random 700-799)
- **Mean Reward**: $46725.12
- **Win Rate**: 29.00%

### Economic Attribution
EV: -$730. Minimum-distance assignment successfully reduced global travel but reduced Final Money. Distributing travel load evenly via Hungarian eliminated instant task execution (Greedy allows one worker to travel 0 steps while another travels 20, whereas Hungarian forces both to travel 10). The delay caused a 48% spike in Water Backlog.

### Repository State
- **Branch**: feature/assignment-optimization
- **Commit**: `N/A`
- **Tag**: `N/A`

---

## EXP-004 [Bug Fix] - Seed Procurement Arithmetic
**Date**: 2026-08-07 | **Champion**: champion-worker-density-v2 | **Decision**: PROMOTE

### Benchmark Details
- **Parameter Values Tested**: Strict dictionary lookup vs Double-counting loop
- **Sample Size**: 100 (Seeds: Random 400-499)
- **Mean Reward**: $47088.53
- **Win Rate**: 94.00%
- **p-value**: 0.000010

### Economic Attribution
+$1,004 improvement. The base Champion iterated through the seed dictionary and incorrectly double-counted Melon seeds (adding both `.get('MELON')` and the loop value). This math error forced it to systematically under-buy seeds, leaving workers idle without seeds to plant. Fixing to a strict lookup eliminated empty tile starvation.

### Repository State
- **Branch**: feature/production-audit
- **Commit**: `2c918bb`
- **Tag**: `champion-seed-fix-v3`

---

## EXP-003 [Policy] - Crop Portfolio Ratio
**Date**: 2026-08-07 | **Champion**: champion-worker-density-v2 | **Decision**: REJECT

### Benchmark Details
- **Parameter Values Tested**: Wheat vs Melon combinations (Static/Dynamic)
- **Sample Size**: 40 (Seeds: Random 300-339)
- **Mean Reward**: $39154.55
- **Win Rate**: 0.00%

### Economic Attribution
All Wheat portfolios collapsed by up to -$40,000. The mathematical ROI model identified Wheat as a Capital compounder, but the game starts with $3,000, meaning the farm is instantly Labor-starved. Every action spent planting Wheat ($15 profit/action) instead of Melon ($101 profit/action) destroys massive opportunity cost.

### Repository State
- **Branch**: feature/production-audit
- **Commit**: `N/A`
- **Tag**: `N/A`

---

## EXP-002 [Policy] - Expansion Utilization Threshold
**Date**: 2026-08-07 | **Champion**: champion-worker-density-v2 | **Decision**: REJECT

### Benchmark Details
- **Parameter Values Tested**: 60%, 70%, 80%, 90%, 100%
- **Sample Size**: 40 (Seeds: Random 200-239)
- **Mean Reward**: $29415.22
- **Win Rate**: 0.00%

### Economic Attribution
-$17,270 collapse across all thresholds due to systemic Expansion-Labor Deadlock. The solitary farmer could never physically achieve the 60%+ utilization required to trigger Quadrant 2 purchase. Because Quadrant 2 was never purchased, the Worker Density logic never hired additional labor. The farm permanently starved for labor while waiting for utilization that required labor to achieve.

### Repository State
- **Branch**: feature/production-audit
- **Commit**: `N/A`
- **Tag**: `N/A`

---

## EXP-001 [Parameter] - Worker Density (Tiles per Worker)
**Date**: 2026-08-06 | **Champion**: v1-baseline | **Decision**: PROMOTE

### Benchmark Details
- **Parameter Values Tested**: 8, 10, 12, 14, 16, 20
- **Sample Size**: 100 (Seeds: Random 0-99)
- **Mean Reward**: $46685.25
- **Win Rate**: 97.00%
- **p-value**: 0.000000

### Economic Attribution
+$5,060 from dynamic labor scaling preventing early capital starvation. Lower worker counts in early game preserved cash for rapid land expansion, while scaling up later allowed full utilization of newly acquired quadrants without bottlenecking on movement or water limits.

### Repository State
- **Branch**: feature/production-audit
- **Commit**: `8636aaf`
- **Tag**: `champion-worker-density-v2`

---

