# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 2.x | Yes |
| 1.x | No |
| 0.x | No |

## Reporting a vulnerability

Use GitHub private vulnerability reporting for the repository. Do not open a public issue and do not include real API keys, private prompts, tenant documents, or production snapshots in a report.

Include the affected version, impact, minimal reproduction with synthetic data, and any proposed mitigation. You should receive an acknowledgement within seven days. A confirmed issue will be assessed for a private fix, regression test, advisory, and coordinated release before public detail is added.

## Deployment boundary

The bundled HTTP server provides a reference bearer boundary, request/body/rate/concurrency limits, secure response headers, redacted auditing, and guarded provider calls. It does not replace TLS, user identity, tenant authorization, a secret manager, process/network isolation, immutable audit storage, or disaster recovery.

External retrieval output is untrusted by default. Never mark it trusted solely because a similarity score is high. Do not send evidence rejected for trust, sensitivity, or injection risk to a fallback model.

Learned-router artifacts are opt-in and cannot bypass deterministic authorization or answer guards. Treat artifact replacement as a supply-chain change: review provenance, pin the model ID, and test route distribution before deployment.

See the full [threat model](docs/threat-model.md) and [deployment checklist](docs/gateway.md).
