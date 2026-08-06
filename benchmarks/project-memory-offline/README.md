# Project Memory offline gate suite

This deterministic Python suite checks routing behavior without a model or network connection. It covers a valid trusted bridge, missing evidence, untrusted evidence, sensitive evidence, an unlinked pair, an evidence-budget overrun, and a Hebrew bridge. Untrusted or sensitive evidence must route to `blocked`, not to a model fallback.

```bash
python benchmarks/project_memory_offline/run.py
```

The suite measures local ingestion and recall latency and confirms that provider token usage is zero. It does **not** measure answer accuracy and must not be presented as a replacement for the live oracle.
