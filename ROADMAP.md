# Roadmap

NESTRA 2.0 is a complete Python SDK, CLI, authenticated gateway, and optional hybrid learned router. The roadmap tracks evidence-backed extensions, not missing release requirements.

## Evaluation

- Run a preregistered disjoint non-inferiority study for Micro.
- Add multilingual and domain-specific Retrieval-only suites.
- Publish provider-neutral cost adapters without hard-coding volatile prices.
- Collect a larger balanced router dataset, add confidence intervals and drift slices, and promote the learned artifact only after its precision gate passes.

## Integrations

- Reference adapters for pgvector, Qdrant, Pinecone, and hybrid lexical/vector retrieval.
- Additional model providers behind the existing protocol.
- OpenTelemetry exporter and durable audit-sink adapter.

## Storage and operations

- Optional encrypted and tenant-aware stores.
- Snapshot migrations with compatibility fixtures.
- Streaming HTTP responses after a security and accounting design review.
- Async provider/retriever protocols after measuring real concurrency requirements.

Items enter a release only with tests, documentation, security review, and representative evaluation. The roadmap does not promise dates.
