# Security and observability

## Request and evidence controls

- Questions are normalized, stripped of unsafe control characters, and length-limited.
- Project IDs use a strict URL-safe grammar and cannot escape the store root.
- Trust and sensitivity filters run before retrieval evidence is sent to any provider.
- Relevant evidence that exists only outside the authorized set is blocked rather than replaced with unrelated safe context.
- Common instruction-override, role-spoofing, tool-coercion, and secret-exfiltration patterns in evidence are blocked.
- Injection checks normalize Unicode format characters, common leetspeak and separator obfuscation, English priority overrides, and common Hebrew instruction overrides.
- External retriever rows default to untrusted.
- Tool and filesystem policies remain deterministic and allow-list based.

## Gateway controls

- Bearer authentication is required unless explicit loopback-only development mode is selected.
- Tokens are compared with a constant-time operation.
- Request bodies, request rates, and concurrent execution are bounded.
- Responses carry no-store, content-type, frame, referrer, and CSP headers.
- Provider calls use a timeout, bounded retries for transient errors, explicit output limits, and no provider-side storage in the bundled OpenAI adapter.
- Meso and Full responses must have valid citation IDs and lexical/numeric support in the cited atoms; model-reported confidence alone never establishes verification.
- Estimated total-token limits are checked before provider calls and observed usage is checked again afterward.
- Restored project snapshots are checked for exact fields, content hashes, provenance, sentence reconstruction, graph consistency, and count integrity before use.
- Public Micro evidence omits compiler-only prompt text and untruncated source text.

## Monitoring contract

Every result includes route, attempted routes, model count, model names, input/output/reasoning/cached/total token counts, latency, alerts, verification state, and cited evidence. Aggregate metrics expose route distribution, blocks, errors, verified results, averages, and alert counts.

Audit events store request IDs, project IDs, route, status, verification, latency, call count, token total, and alert names. Recursive redaction removes credentials and common content fields including prompt, input/output, text, question, answer, evidence, memory, messages, and token. Do not add raw user or evidence content to operational events.

## Host responsibilities

NESTRA does not provide operating-system isolation, a secret manager, TLS termination, identity provisioning, tenant authorization, egress filtering, immutable audit storage, backups, or a moderation policy. Production deployments must supply these controls at the platform boundary.
