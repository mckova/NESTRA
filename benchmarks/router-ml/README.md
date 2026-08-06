# Learned Router benchmark

This benchmark trains a local Python Logistic Regression model to predict whether Micro will pass its deterministic accuracy lock without falling outside the available Full-route quality margin.

```bash
python scripts/train_router.py
python benchmarks/router_ml/run.py
```

The committed demo artifact uses 18 historical oracle examples for training, six disjoint examples for threshold calibration, and a second six-example disjoint holdout. It is intentionally `experimental` and opt-in. The value is the reproducible feature, label, training, calibration, holdout, artifact, and runtime-veto pipeline — not a production performance claim from a tiny sample.
