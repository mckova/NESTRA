# Router artifacts

`micro-safety-demo.json` is a reproducible, data-only Logistic Regression artifact for NESTRA 2.0. It is marked `experimental`, is never loaded by default, contains no raw text, and currently disables Micro because its calibration split did not meet the required precision and support constraints.

Rebuild and evaluate it from the repository root:

```bash
python scripts/train_router.py
python benchmarks/router_ml/run.py
```

The training script writes identical repository and package-resource copies. Do not promote the artifact by editing JSON. Follow the checklist in `docs/learned-router.md`, preserve disjoint dataset IDs, and checksum or sign reviewed candidates before deployment.
