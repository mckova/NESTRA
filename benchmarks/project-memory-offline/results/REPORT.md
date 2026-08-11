# Offline Project Memory gate result

- Run date: 2026-08-11
- Cases: 8 deterministic fixtures
- Provider calls/tokens: 0

| Case | Expected | Actual | Result |
|---|---|---|---|
| Trusted two-document bridge | Micro | Micro | Pass |
| Missing second fact | Fallback | Fallback | Pass |
| Untrusted evidence | Blocked | Blocked | Pass |
| Sensitive evidence | Blocked | Blocked | Pass |
| No structural bridge | Fallback | Fallback | Pass |
| Evidence over Micro budget | Fallback | Fallback | Pass |
| Irrelevant retrieval request | Blocked | Blocked | Pass |
| Hebrew two-document bridge | Micro | Micro | Pass |

All 8/8 routes matched their declared expectations. On the recorded local run, average deterministic ingestion latency was about 0.42ms and average recall latency was about 0.18ms. These latency values are machine- and run-specific; the raw values remain in `latest.json`.

This suite validates routing and safety invariants only. It does not call a model, score an answer, or establish that the accepted Micro route preserves accuracy. That claim remains blocked on a new live disjoint oracle run.
