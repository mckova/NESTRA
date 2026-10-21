# Architecture

## One in-memory, offline path

```text
Invented English documents + explicit fixture metadata
                        |
                        v
          NESTRA project-memory compiler
                        |
                        v
              Lexical evidence recall
                        |
                        v
              Showcase policy decision
                 /       |       \
       sources_found  no_evidence  blocked
                 \       |       /
                        v
          English text or deterministic JSON
```

There is no provider stage that generates an answer. The output reports `configured: false` and zero provider calls. There is no HTTP service, network client, file ingestion interface, model download, or persistence layer in the demo path.

## Reused core

The `nestra_core` package is a deliberately narrow import boundary. Its empty package initializer avoids the broad imports of upstream NESTRA. Three files are copied verbatim:

- `project_memory.py`: document validation, deterministic fact/provenance compilation, lexical recall and snapshot validation.
- `memory.py`: the in-memory scoped-memory dependency used by project-memory code. It does not write user memory to disk.
- `security.py`: project identifier validation, text sanitization and heuristic injection detection.

Relative imports stay inside this copied package. `PROVENANCE.json` binds these bytes to the reviewed source snapshot. The newly authored wrapper does not import the original checkout, upstream provider code or the full runtime.

The authored documentation, demo, fixtures, CLI help/output and tests are in English. Multilingual regular-expression patterns inside the inherited core are algorithm data retained verbatim. Retaining those patterns preserves the copied implementation; it does not demonstrate multilingual retrieval quality.

## Showcase policy is explicit

The core recall algorithm includes a small source-quality component in its score. A nonzero retrieval score therefore does not establish a relevant match. The new wrapper has its own stated policy for choosing displayable evidence and for abstaining.

The wrapper's default relevance rule requires full lexical coverage of the informative query terms by an excerpt. This conservative rule is implemented in the showcase wrapper, not in upstream runtime routing or `evaluate_pre_call_gate`. It is a small demonstration contract, not a claim that word overlap establishes semantic entailment.

Trust and sensitivity are supplied by controlled fixtures. The showcase policy checks these boundaries before releasing excerpts to the presentation layer. A blocked or unsupported result must not include a snippet merely to explain why it was withheld. Fixed reason codes explain the decision without claiming factual verification.

The inherited injection detector uses a limited set of patterns. It is a demonstration aid, not comprehensive protection against arbitrary malicious text. No execution tools or model calls are available to the demo.

## Determinism and testing boundary

Fixture identifiers and source references are stable. Compilation uses a fixed clock rather than the current wall clock. This fixture time is not a live audit timestamp. Sorting and formatting are deterministic; the same selected fixture produces the same result in repeated runs.

Checks should cover both domain outcomes and invariants: citations point to permitted fixture sources, unsupported and blocked paths disclose no excerpts, results repeat exactly, and no provider is configured. Additional static and runtime checks can establish the lack of network operations within this small demo, without asserting that all upstream NESTRA configurations are offline.

This is a retrieval-and-policy showcase. It does not evaluate semantic entailment, general language understanding or answer generation.
