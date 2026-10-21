# NESTRA offline showcase

A small, deterministic English demonstration of **source retrieval and policy decisions** over invented team procedures. It uses a reviewed subset of NESTRA's lexical project-memory code. It does not generate an answer with an LLM.

The demo shows a supported question with source excerpts, a question without sufficient evidence, and a relevant source that policy does not allow. Source snippets are shown only when the showcase policy permits them.

## Run

Use an existing Python 3.10 or newer interpreter. No packages, model downloads, account, API key, or installation are required. From this directory:

```powershell
python -I -B demo.py
python -I -B demo.py --json
python -I -B demo.py --case supported
python -I -B demo.py --help
```

The text presentation is in English; JSON is suitable for inspection and testing. `--case` selects `supported`, `insufficient`, `untrusted`, or `restricted`. Both modes use the same application decisions.

The launcher adds only this directory's `src` to its import path. `-I` isolates Python from user-level configuration and `PYTHONPATH`; `-B` prevents bytecode files. The demo reads no external documents or environment credentials, writes no persistent memory, and opens no server. Its fixture source references are labels, not URLs to fetch.

## What to inspect

| Layer | Behavior |
|---|---|
| Retrieval | The copied NESTRA compiler builds an in-memory index of synthetic documents; lexical recall proposes evidence. |
| Showcase policy | New wrapper code applies the explicit relevance, trust and sensitivity decisions used by this demo. It controls whether snippets may be displayed. |
| Provider | Not configured. No real or simulated LLM is used; provider calls remain zero. |

The four fixtures respectively demonstrate permitted evidence, insufficient evidence, an untrusted source and a sensitivity-restricted source. Policy reason codes are included in JSON; `generated_answer` is always `null`.

`sources_found` means the demo found permitted source evidence. It does not mean a generated answer is correct or that the evidence semantically entails every part of a question. `no_evidence` and `blocked` return no source excerpts.

For a quick review, compare [text output](examples/demo-output.txt), [JSON output](examples/demo-output.json), [architecture](docs/ARCHITECTURE.md), and [limitations](docs/LIMITATIONS.md).

## Checks

```powershell
python -I -B run_checks.py
```

The checks use Python's standard-library test runner. They exercise the extracted subset and new showcase behavior, not the full upstream NESTRA product. See the [validation report](docs/VALIDATION.md) for the actual run result; the presence of a test file alone is not a passing result.

## Scope and provenance

- `src/nestra_core/project_memory.py`, `memory.py` and `security.py` were copied without edits from a local NESTRA snapshot.
- `PROVENANCE.json` records the allowlist and SHA-256 digest of each copied file, including the preserved license.
- `src/nestra_showcase`, launchers, fixtures, tests and documentation are newly authored for this isolated showcase.
- The full upstream runtime, HTTP gateway, provider adapters, learned router, benchmarks and user memory were not copied.

The original source directory is not an import dependency. The private review evidence outside this showcase records hashes of the explicit copied-file allowlist and a before/after filesystem-metadata comparison of the source tree. It is not a full content-hash audit of every original file. Git history was not inspected.

All fixture names, procedures and content are invented for this demonstration. Trust and sensitivity are fixture metadata supplied by the author, not automatically verified facts about a real organization.

The authored documentation, demo, fixtures, CLI help/output and tests are in English. Multilingual regular-expression patterns inherited from the copied core are algorithm data retained verbatim. They are not demo prose and do not establish multilingual retrieval quality.

## Attribution and release status

The upstream [MIT license](LICENSE) and its original copyright notice are preserved. See [NOTICE](NOTICE) and [PROVENANCE.json](PROVENANCE.json). No ownership reassignment is implied.

This standalone showcase runs locally and stays separate from the upstream runtime. There are no claims here about model accuracy, production security, or token-cost savings.
