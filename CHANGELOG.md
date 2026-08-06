# Changelog

All notable changes follow Keep a Changelog conventions. The project uses semantic versioning for its Python, CLI, storage, and HTTP contracts.

## [2.0.0] - 2026-08-06

### Changed

- Rebranded the project as NESTRA (Nature-inspired Evidence Selection, Trust-aware Routing Architecture) to reflect that it is an adaptive inference layer, not an agent-only framework.
- Renamed the Python package, CLI, environment variables, HTTP identity, schemas, Docker resources, benchmarks, and documentation to the NESTRA namespace.
- Reimplemented the SDK, runtime, CLI, HTTP gateway, storage, provider adapter, memory system, routing, guards, and learned router as a native Python 3.10+ package.
- Replaced npm packaging and Node CI with `pyproject.toml`, wheel/sdist builds, Python 3.10–3.13 CI, and Python-native examples.
- Ported the offline suite, learned-router training/holdout, and live NESTRA oracle to Python while retaining historical raw evaluation data.
- Renamed Python call-site arguments to snake_case while preserving camelCase wire JSON and schema compatibility.

### Removed

- Removed the JavaScript/ESM runtime, tests, examples, scripts, and npm metadata. Version 2.0 is therefore a deliberate language-level breaking release.

### Fixed

- Restored the documented 24-hour default TTL while preserving explicit permanent memory with `ttlMs=None`.

## [1.1.0] - 2026-08-06

### Added

- Optional local Logistic Regression router with a versioned 15-feature schema and dependency-free inference.
- Three-way Micro/Meso/Full probability calibration with automatic Micro disablement when the precision constraint is unmet.
- Deterministic vetoes preserving Blocked/Retrieval routes, evidence trust, sensitivity, coverage, structural-chain, and token eligibility.
- Reproducible training, calibration, disjoint-holdout benchmark, JSON model artifact/schema, and aggregate reports without raw question or evidence text.
- CLI/SDK model loading plus router source, model ID, thresholds, probability, confidence, veto, audit, and aggregate-monitoring fields.

### Security

- Learned routing cannot authorize rejected evidence or bypass post-call accuracy guards.
- The bundled model remains experimental and opt-in because current calibration data cannot support a savings claim.

## [1.0.0] - 2026-08-06

### Added

- Production `NestraRuntime` with Blocked, Retrieval-only, Micro, Meso, and Full routes.
- Accuracy-locked escalation and fail-closed `needs_review` results.
- Zero-model-token retrieval with evidence and provenance.
- Provider-neutral model and retriever contracts plus an OpenAI Responses adapter.
- Structured outputs, explicit GPT-5.6 tier/reasoning configuration, timeout, retry, and normalized usage.
- Atomic project-memory store, deterministic compilation, scoped memory, trust, sensitivity, TTL, decay, and deletion.
- Prompt-injection checks, strict project IDs, rate and concurrency limits, redacted audits, metrics, hooks, and tool/path policies.
- Installable `nestra` CLI, authenticated HTTP gateway, OpenAPI contract, JSON schemas, Docker and Compose deployment.
- Unit, integration, provider, storage, CLI, gateway, security, memory, routing, and benchmark tests.
- Contributor, conduct, support, security, architecture, API, CLI, deployment, evaluation, and threat-model documentation.
- GitHub CI across supported Node versions, Docker build verification, issue/PR templates, Dependabot, and tagged release artifacts.

### Changed

- Moved the compact evidence compiler from benchmark code into the public production core; the benchmark now re-exports and measures that implementation.
- Reframed the 50–100 token band as an experimental Micro target guarded by escalation, not a project-wide guarantee.

## [0.1.0] - 2026-08-05

- Separated NESTRA from Agent Hive.
- Added the initial colony topology, scoped memory, goal budgets, hooks, guardrails, redacted audits, and research oracle.
