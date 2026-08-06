# NESTRA low-token oracle

The first 12-question disjoint validation run was generated before the repository split, so the raw artifact uses the temporary labels `adaptiveMemoryHive` and `microHive100`. In NESTRA they map to `adaptiveMemoryNestra` and `microNestra100` respectively. The raw file is preserved unchanged under `migration-source`.

| System | Avg tokens/question | Exact match | Token F1 | Task loss | Avg latency |
|---|---:|---:|---:|---:|---:|
| Direct GPT | 73.6 | 50.0% | 0.576 | 0.424 | 2.437 s |
| Adaptive Memory NESTRA | 1,416.0 | 58.3% | **0.842** | **0.158** | 4.260 s |
| MicroNestra-100 | **87.6** | 58.3% | 0.686 | 0.314 | 2.865 s |
| Accuracy-locked cascade | 1,083.5 | 58.3% | **0.842** | **0.158** | 5.705 s |

MicroNestra-100 stayed at or below 100 tokens on 11/12 calls; the maximum was 102. It improved over direct answering but failed the no-accuracy-loss requirement. The deterministic lock accepted 4/12 compact answers with mean F1 0.95. Escalating the remaining eight reproduced the Adaptive result on this sample and reduced its average token use by 23.5%, but the cascade remained far above the 50–100 token target.

This is a falsification result, not a product claim. The next test must compile stable project knowledge once and report both query-time and amortized ingestion tokens over at least 100 disjoint questions and repeated seeds.

## Pre-gated Project Memory status

The next implementation now exists as `preGatedMicroNestra`: it compiles facts/entities/relations locally, recalls a two-document chain, and applies a trust/sensitivity/coverage/structure/budget gate before any Micro call. A 7-case offline routing suite passes, including poisoned, sensitive, incomplete, oversized, unlinked, and Hebrew evidence.

A live three-question development run was attempted on 2026-08-05 but stopped before dataset download or model calls because the execution environment's external-usage approval was unavailable. No partial result was written. Therefore this report makes no new latency, token, or answer-quality claim for `preGatedMicroNestra` yet.
