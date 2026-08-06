# Learned router

NESTRA can place a small learned policy between deterministic retrieval/security checks and the Micro, Meso, and Full generation tiers. The objective is constrained optimization: reduce expected provider tokens and latency only when the calibrated probability of Micro success satisfies the quality threshold.

## What is learned — and what is not

The model predicts `p(Micro-safe)`. A positive label requires the deterministic Micro accuracy lock to accept and, when both raw scores exist, Micro token F1 to be no more than 0.05 below Adaptive Full.

ML never owns:

- Blocked and Retrieval-only routing.
- Evidence trust, sensitivity, prompt injection, or tenant policy.
- Minimum fact/document count, structural chain, coverage, and evidence-token eligibility.
- Citation, grounding, confidence, call-budget, and fail-closed post-call guards.

The model proposes a generation tier; deterministic policy can veto it. A malformed, malicious, or inaccurate artifact cannot authorize rejected evidence or bypass answer verification.

## Model and features

The implementation is weighted, L2-regularized binary Logistic Regression written in dependency-free Python. Inference performs feature standardization, a dot product, and a sigmoid; it spends zero LLM tokens.

Feature schema 1 contains 15 bounded numeric fields: normalized question length and term count; reasoning and binary-question cues; retrieval intent; safe and expanded query/intent coverage; structural-chain presence; evidence size; atom, document, and bridge counts; and maximum sensitivity. The artifact contains coefficients, normalization statistics, thresholds, aggregate metrics, and provenance — never raw question, answer, or evidence text.

## Three-way calibrated policy

- `p >= microProbabilityMinimum`: propose Micro, subject to deterministic eligibility.
- `p <= fullProbabilityMaximum`: select Full conservatively.
- Between thresholds: abstain to Meso when eligible, otherwise Full.

Calibration requires at least 0.90 observed Micro precision and at least three selected calibration cases. If no threshold satisfies both constraints, `microEnabled` is false and the threshold is set above 1. This is intentional fail-closed behavior.

## Reproduce

```bash
python scripts/train_router.py
python benchmarks/router_ml/run.py
python -m pytest
```

Training uses 18 historical oracle examples. A separate six-example split calibrates thresholds; a second disjoint six-example split evaluates the committed artifact. Outputs:

- `models/router/micro-safety-demo.json`
- `src/nestra/models/micro-safety-demo.json`
- `benchmarks/router-ml/results/REPORT.md`
- `benchmarks/router-ml/results/HOLDOUT_REPORT.md`

Opt in from the CLI:

```bash
nestra route --project casting --question "What is Sissy Spacek's middle name?" \
  --router-model models/router/micro-safety-demo.json
```

Or from Python:

```python
from nestra import NestraRuntime, load_bundled_router_model

runtime = NestraRuntime(store=store, router_model=load_bundled_router_model())
```

## Current result and claim boundary

The training split has 6 positive and 12 negative labels; calibration has 1 positive and 5 negatives. Calibration could not find a Micro threshold satisfying 0.90 precision, so the bundled artifact disables Micro. The independent holdout contains six Micro-unsafe examples: the policy routed all six to Full, with unsafe-Micro rate 0 and Full-unsafe recall 1.0. Because it selected no Micro cases, it demonstrated no token reduction.

Raw classifier accuracy on that holdout is 0.167 while policy-decision accuracy is 1.0. The first thresholds probabilities at 0.5; the second measures conservative Full/Micro actions. Neither metric establishes end-answer non-inferiority.

The honest conclusion: training, calibration, artifact validation, runtime integration, monitoring, and safety fallback are implemented, but the dataset is too small and imbalanced to demonstrate savings. The model remains experimental and opt-in.

## Promotion checklist

1. Freeze a larger, representative, disjoint dataset with multilingual and domain slices.
2. Measure answer loss, tokens, latency, unsafe-Micro rate, abstention, and Full over-routing against deterministic NESTRA and RAG + LLM.
3. Require preregistered Micro precision and non-inferiority margins with confidence intervals.
4. Test poisoned, sensitive, injected, missing, and distribution-shifted evidence.
5. Checksum or sign the reviewed artifact and deploy it with rollback and drift alerts.
