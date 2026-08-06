# Learned Router report

- Model: `router-5cde0ce5edce5665`
- Status: **experimental**
- Implementation: **Python**
- Feature schema: 1

## Data

- Training: 18 examples (6 Micro-safe, 12 unsafe).
- Calibration: 6 examples (1 Micro-safe, 5 unsafe).
- Raw questions, answers, and evidence are not stored in the model artifact.

## Calibrated routing

- Full when `p(Micro-safe) <= 0.975348`.
- Micro when `p(Micro-safe) >= 1.000001`; disabled because calibration did not meet precision/support constraints.
- Meso between the thresholds. Blocked and Retrieval-only remain deterministic.

## Metrics

| Split | Classifier accuracy | Brier | Micro precision | Unsafe Micro rate | Full unsafe recall | Policy-decision accuracy |
|---|---:|---:|---:|---:|---:|---:|
| Train | 0.944 | 0.081 | 0.000 | 0.000 | 1.000 | 0.667 |
| Calibration | 0.500 | 0.381 | 0.000 | 0.000 | 0.800 | 0.800 |

This real, reproducible Python training pipeline remains experimental. The sample is too small for a savings or non-inferiority claim.
