# NESTRA oracle

The live Python oracle compares Direct GPT-5.6, local BM25 RAG + GPT-5.6, Fixed NESTRA, Adaptive Memory NESTRA, Pre-Gated Micro, Micro-100, and Accuracy-Locked Micro on the same seeded HotpotQA questions.

Every model call uses the configured model and reasoning effort. Results record latency, model calls, provider-reported token categories, exact match, token F1, and task loss (`1 - tokenF1`).

```powershell
$env:OPENAI_API_KEY = "..."
python -m benchmarks.nestra_oracle.benchmark --limit 12 --methods directGpt56,ragGpt56,fixedNestra,adaptiveMemoryNestra,preGatedMicroNestra,microNestra100,accuracyLockedMicroNestra
```

`preGatedMicroNestra` compiles the corpus into Project Memory locally. If recalled evidence fails the deterministic pre-call gate, it routes directly to Adaptive NESTRA and avoids the Micro call. If the gate passes, Micro remains protected by the post-call grounding lock.

Network and API failures do not overwrite historical evidence automatically. Files under `results/migration-source` preserve pre-separation runs exactly as generated. Old Hive labels inside those immutable JSON files are provenance, not current architecture.
