# Experiment J1+J2 — Logistics Scalability Report

## J1: V1 (Hybrid) Scalability Curve — Fixed 12 Melons

| Workers | Mean $  | Δ vs 2w | Prod/Worker | Move% | Revenue/Worker |
|---------|---------|---------|-------------|-------|----------------|
| 1 | $34706 | +1292 | 184.1 | 48.1% | $17353 |
| 2 | $33414 | +0 | 119.0 | 50.2% | $11138 |
| 3 | $33574 | +160 | 89.0 | 48.6% | $8393 |
| 4 | $34700 | +1286 | 73.6 | 46.2% | $6940 |
| 6 | $34687 | +1273 | 52.6 | 46.3% | $4955 |
| 8 | $33218 | -196 | 39.9 | 46.1% | $3691 |
| 10 | $33129 | -285 | 32.6 | 45.0% | $3012 |

## J2: Scheduler Comparison

| Workers | V1_Hybrid | V2_TileCentric |
|---------|-------|-------|
| 1 | $34706 | $20998 |
| 2 | $33414 | $20613 |
| 3 | $33574 | $20611 |
| 4 | $34700 | $20608 |
| 6 | $34687 | $20595 |
| 8 | $33218 | $20561 |
| 10 | $33129 | $20472 |

## Key Observations

* **Peak V1 reward:** $34706 at 1 workers
* **First negative marginal worker count (V1):** 2 workers
* **Control (2w V1):** $33414

### Scheduler winner at each worker count:
  * 1 workers → **V1_Hybrid** ($34706)
  * 2 workers → **V1_Hybrid** ($33414)
  * 3 workers → **V1_Hybrid** ($33574)
  * 4 workers → **V1_Hybrid** ($34700)
  * 6 workers → **V1_Hybrid** ($34687)
  * 8 workers → **V1_Hybrid** ($33218)
  * 10 workers → **V1_Hybrid** ($33129)