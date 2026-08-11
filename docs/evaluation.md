# Evaluation policy

Optimization claims are accepted only when quality, latency, model calls, and token categories are measured on the same examples and settings.

## Metrics

- Task success or exact match.
- Token F1 and `taskLoss = 1 - tokenF1`.
- End-to-end and model latency.
- Input, output, reasoning, cached, and total provider tokens.
- Model calls, escalations, blocks, guard failures, and `needs_review` rate.
- Retrieval-only coverage and citation validity.

Local lexical scanning and compilation are recorded separately from provider tokens. Ingestion cost is amortized across queries; it is never silently counted as zero.

## Suites

```bash
python benchmarks/project_memory_offline/run.py
python scripts/train_router.py
python benchmarks/router_ml/run.py
python -m benchmarks.nestra_oracle.benchmark --limit 12
```

The Project Memory suite requires no network or model. Its eight deterministic cases include poisoned, sensitive, incomplete, oversized, unlinked, Hebrew, and topically irrelevant retrieval evidence. The live oracle requires an API key and compares Direct GPT-5.6, BM25 RAG + GPT-5.6, Fixed NESTRA, Adaptive NESTRA, pre-gated Micro, Micro-100, and an accuracy-locked cascade on a seeded HotpotQA selection.

The learned-router suite trains locally on 18 historical examples, calibrates on six separate examples, and evaluates on six disjoint examples. Classifier calibration and policy decisions are reported separately: Micro precision and unsafe-Micro rate measure safety; Micro route rate estimates potential savings; Full over-routing measures conservatism.

## Current evidence

Historical 12-question results found Micro-100 averaged 87.6 tokens and token F1 0.686, while Adaptive averaged 1,416 tokens and F1 0.842. An accuracy-locked cascade matched Adaptive on that sample but averaged more than the desired Micro band. These are useful engineering signals, not statistical proof.

The bundled learned artifact did not meet the 0.90 calibration precision threshold, so Micro is disabled. It made zero unsafe Micro selections on a six-example all-unsafe holdout and therefore achieved zero savings. Do not describe raw classifier accuracy as routing safety or policy-decision accuracy as answer quality.

## Adding a claim

Commit the fixture IDs or dataset revision, seed, model snapshot or alias, reasoning effort, prompts, budgets, raw JSON, aggregation code, and report. Record failures and aborted runs. Never overwrite a previous report merely because a later result is better.

Before claiming quality preservation, run a preregistered, disjoint non-inferiority study with enough examples, report confidence intervals, and publish failures alongside successes.
