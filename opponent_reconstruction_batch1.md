# Ablation Results (Batch 1)

## Experiment A: Control (Baseline 2-Worker/12-Melon)
* **Mean Reward:** $34706.40
* **Min/Max:** $34560.00 / $35292.00
* **Hires:** 1.0
* **Max Cash:** $34786.40
* **Movement / Productive:** 0.0 / 724.8

## Experiment B: Starting Liquidation
* **Mean Reward:** $34706.40
* **Min/Max:** $34560.00 / $35292.00
* **Hires:** 1.0
* **Max Cash:** $34786.40
* **Movement / Productive:** 0.0 / 724.8

## Comparison
* **Delta:** $0.00
* **Win Rate (B > A):** 0.0%

### Analysis
Experiment B attempted to isolate the `LIQUIDATE_STARTING_WHEAT` mechanism. 
However, the Delta is exactly $0.00. This occurs because the Control (the 5 PM baseline) **already inherently liquidates all starting non-fertilizer inventory** via its default sell loop. Both A and B instantly sell the 152 starting wheat on day 0, generating a ~$3,040 cash injection. 

Crucially, because neither A nor B have `DYNAMIC_WORKERS` or `DYNAMIC_LAND` enabled, they simply sit on the excess capital rather than reinvesting it to scale capacity. The capital alone without the engine to use it provides $0 marginal reward.
