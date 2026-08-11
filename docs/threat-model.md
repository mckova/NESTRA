# Threat model

## Protected assets

Provider credentials, tenant documents, memory snapshots, user questions, generated answers, audit integrity, token budget, and availability.

## Trust boundaries

The client, gateway process, project store, external retriever, and model provider are distinct boundaries. Retrieval score is not trust. A stronger model is not a security boundary. A fallback never receives evidence rejected by policy.

## In-scope threats

- Prompt injection embedded in evidence.
- Poisoned, over-sensitive, or cross-tenant retrieval results.
- Path traversal through project identifiers.
- Credential and prompt leakage through logs or provider errors.
- Oversized requests, request floods, concurrency exhaustion, unbounded loops, and token overruns.
- Invalid citations, unsupported answers, malformed structured output, and stale memory.
- Unauthenticated access to stored projects or model spending.
- Poisoned, replaced, or distribution-shifted learned-router artifacts that over-select Micro.

## Mitigations

Input normalization, strict IDs, topical retrieval checks, safe retrieval filters, obfuscation-aware injection flags, citation grounding, pre-call token limits, timeouts, bounded retry, gateway-wide rate limits, bounded request workers, body-framing caps, bearer authentication, constant-time token comparison, deep snapshot validation, atomic storage, provenance, TTL/decay, recursive audit redaction, and no raw content in metrics.

Learned artifacts are data-only, schema-validated, opt-in, and unable to override Blocked/Retrieval routes or deterministic evidence eligibility. Router model ID, route source, and veto reason are observable. Production deployments should verify artifact provenance or signatures and alert on drift.

## Out of scope for the reference implementation

TLS, user identity, per-tenant authorization, operating-system sandboxing, egress control, malware scanning, cryptographic storage encryption, key rotation, moderation policy, DDoS protection, immutable remote audit, and disaster recovery. Deployers must supply these controls.

## Security regression rule

A route optimization must not weaken evidence authorization, citation validation, storage boundaries, audit redaction, or fail-closed behavior. Add an adversarial test for every fixed vulnerability.
