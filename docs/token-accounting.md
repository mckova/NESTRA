# Token accounting

NESTRA reports three costs separately.

1. **Local ingestion cost:** elapsed time and lexical tokens scanned by the deterministic Project Memory Compiler. It uses zero provider tokens, but it is not described as free compute.
2. **Query-time provider tokens:** tokens reported by model API calls for one question.
3. **Amortized provider tokens:** `(provider tokens used during ingestion + provider tokens used by all questions) / number of questions`.

The current compiler is deterministic and local, so provider ingestion tokens are zero. Future neural extraction or embedding stages must report their provider or compute cost rather than hiding it.

Every query result reports `inputTokens`, `outputTokens`, `reasoningTokens`, `cachedInputTokens`, and `totalTokens` for all attempted routes. Retrieval-only and Blocked results must report zero model calls and zero provider tokens. A Micro result that exceeds its configured 50–100 target is returned with a `micro_token_target_exceeded` alert; the measurement is never clipped to the target.

HotpotQA gives each question a different corpus, so it cannot demonstrate amortized project-memory reuse. It is useful for retrieval falsification only. The next evaluation needs many questions over the same compiled project and must report ingestion latency, storage size, recall latency, query tokens, escalation rate, and amortized tokens per question.
