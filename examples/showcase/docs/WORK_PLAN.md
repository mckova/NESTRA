# Work plan for the NESTRA offline showcase

## Goal and boundaries

A deterministic English CLI demonstration based on a reviewed subset of NESTRA and invented team procedures. It shows source-backed retrieval, insufficient evidence, and blocking of untrusted or sensitivity-restricted sources. No model provider, paid service, API key, network call or source-checkout dependency exists in the demo path.

This plan records the initial extraction and the later English correction. The correction applies to authored documentation, wrapper, fixtures, CLI help/output and tests. Multilingual regular-expression patterns in the inherited core are algorithm data retained verbatim. The copied core and license are not translated or reassigned.

The original source checkout stays read only and outside this artifact. Its local path and comparison evidence belong to a private review directory and are not required to run the demo. The staged artifact is under `examples/showcase`; private review evidence is not part of that package.

## Stages and responsibilities

| Stage | Owner | Dependency | Acceptance criterion | Status |
|---|---|---|---|---|
| Source review and baseline | Integration reviewer | Existing read access | Explicit allowlist, AST/import review, source metadata and selected SHA-256 hashes | Completed during initial extraction; scope recorded in validation report |
| Isolated source subset | Integration reviewer | Source review | Original license and three core modules copied verbatim; no broad upstream initializer or providers | Completed during initial extraction |
| Demo and invented data | Demo agent | Isolated subset | Four cases, blocked evidence withheld, no provider, deterministic English text and JSON | English correction passed the standalone suite; actual English samples captured |
| Documentation | Documentation agent | Agreed interface | English README, architecture, limits, plan and notice; no installation required | Completed; six owned documents passed the English-script check |
| Independent checks | Test agent | Interface and implementation | Behavior, determinism, provenance, disclosure and offline checks | Corrected staged revision: 23 tests passed |
| Integration review | Integration reviewer | Code, docs and checks | Review changes, run current checks and compare captured output | Corrected stage: 23 tests and complete showcase Ruff checks passed; samples matched |
| Samples and artifact review | Integration reviewer | Successful current checks | Actual English CLI samples, copied-file integrity and bounded artifact inventory | Completed: 22 selected files, English authored content, valid links and unchanged copied-file hashes |

Historical passing results do not establish acceptance of a later revision. Current staged results belong in [VALIDATION.md](VALIDATION.md).

## Explicit copy allowlist

- `LICENSE`, unchanged, including the Agent Hive Contributors notice.
- `src/nestra/project_memory.py` to `src/nestra_core/project_memory.py`.
- `src/nestra/memory.py` to `src/nestra_core/memory.py`.
- `src/nestra/security.py` to `src/nestra_core/security.py`.

The selected modules were inspected before their initial execution. Their dependencies are standard-library or local imports. No filesystem, shell or network operations were identified in the reviewed core AST. The broad original package initializer is excluded, avoiding unrelated server, provider and integration imports.

`PROVENANCE.json` records the selected paths and SHA-256 digests. No `.git`, credentials, user data, caches, logs, private review evidence, benchmarks or provider responses are copied. New wrappers, invented fixtures, launchers and tests belong to the showcase rather than the upstream runtime.

## Acceptance criteria

1. One command runs the demo with an existing interpreter, without installation or network access.
2. Procedures, questions, help and output are English and use invented data only.
3. The supported case displays a source excerpt with provenance, not an LLM-generated answer.
4. The insufficient-evidence case does not report irrelevant sources as success.
5. Blocked cases expose no source excerpts, identifiers, titles or references.
6. JSON and text are deterministic. A fixed fixture clock is not presented as a live audit timestamp or measured latency.
7. Retrieval, showcase policy and the absence of a provider are clearly separated.
8. No model-quality, token-saving, semantic-reliability or production-security claims are inferred from the demo.
9. Copied-file digests and the original license remain unchanged.
10. Authored docs, fixtures, help/output and tests contain no Hebrew script. Inherited multilingual regex algorithm data stays verbatim outside that translation boundary.

## Verification and release boundary

The [validation record](VALIDATION.md) records commands, observed results and their limits. The corrected staged revision passed its standalone suite, local integration checks and release-file review. Repository-wide CI status is recorded by GitHub Actions for the published commit. The demo performs no Git, network or installation operation and never modifies the original source checkout.
