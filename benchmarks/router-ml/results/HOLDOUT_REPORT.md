# Learned Router independent holdout

- Model: `router-5cde0ce5edce5665`
- Status: **experimental**
- Implementation: **Python**
- Examples: 6 (disjoint)

| Classifier accuracy | Brier | Unsafe Micro rate | Full unsafe recall | Policy-decision accuracy | Micro route rate |
|---:|---:|---:|---:|---:|---:|
| 0.167 | 0.479 | 0.000 | 1.000 | 1.000 | 0.000 |

All six examples were Micro-unsafe. The calibrated policy selected no unsafe Micro routes and produced no token savings. This is not evidence of production generalization.
