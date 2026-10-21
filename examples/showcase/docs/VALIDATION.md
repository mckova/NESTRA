# Local validation record

## English correction: staged standalone checks passed

The authored demo, fixtures, CLI help/output, tests and documentation are corrected to English. The independent test agent ran `python -I -B run_checks.py` against the corrected stage: **23 tests passed; exit code 0**. This included the English runtime fixtures/schema, CLI text/help, README language/link checks, authored Python language checks, copied-core hashes, disclosure/abstention and scratch-handling regressions. The agent also reported the selected Ruff lint and formatting checks passed for its owned test files.

The integration reviewer independently reran the corrected stage: **23 tests passed; exit code 0**. Actual English text and JSON output matched the newly captured examples. Both samples were ASCII, had the four expected statuses and reported zero provider calls. The complete showcase Ruff lint and formatting checks below passed. The documentation agent checked its six owned documents for Hebrew script and the removed language link; both checks passed. Final review covered all 22 selected files, checked links and private-path/token patterns, and reconfirmed copied-file hashes. Repository-wide CI status must be checked in GitHub Actions for the published commit; local results do not establish CI success.

The copied core retains its multilingual regular-expression patterns as verbatim algorithm data. The English correction does not translate those patterns, change upstream attribution or replace the original license.

From `examples/showcase`, verify the corrected revision with the existing interpreter:

```powershell
python -I -B run_checks.py
python -I -B demo.py
python -I -B demo.py --json
python -I -B demo.py --help
```

The standalone suite checked determinism, all four policy outcomes, zero provider calls, blocked-source disclosure and copied-file digests. The integration reviewer recaptured both example files from the CLI. Final artifact review confirmed the authored docs, fixtures, help/output and tests contain no Hebrew script. Inherited regex algorithm data is outside that translation boundary.

The integration reviewer ran these checks successfully from the repository root using the existing Ruff installation. No installation is required or authorized by this record:

```powershell
python -I -B -m ruff format --check --isolated --no-cache --line-length 100 --target-version py310 examples/showcase
python -I -B -m ruff check --isolated --no-cache --select E4,E7,E9,F,I --target-version py310 examples/showcase
```

## Historical results: earlier revisions, 2026-10-21

On Windows with the existing Python **3.13.12** interpreter, the independent test agent and integration reviewer each observed **23 tests passed; exit code 0** before the English correction. The earlier staged revision also passed the same suite and the Ruff commands above. Its text and JSON CLI output matched the then-current captured examples. These are historical observations, not current correction results.

The checked contracts included:

- Copied-file hashes, preserved attribution, and standard-library/local imports only.
- Snapshot integrity, mutation isolation and project-identifier validation.
- Fixture provenance, unsupported/near-topic/title-only abstention, and repeatable output.
- Untrusted and sensitivity-restricted source content, identifiers, titles and references absent from returned output.
- Detected source/question instruction patterns blocked; invalid policy numbers rejected.
- Network, environment reads and file I/O denied by runtime test patches during evaluation.
- CLI JSON identical across fresh isolated processes; one-case selection and clean invalid-case failure; empty CLI scratch directories.

Runtime patches exercise evaluation after imports. They are scoped checks, not an operating-system network sandbox or proof about every upstream configuration. Application code was inspected before execution and imported no network client, provider adapter or process launcher.

Python 3.10+ is the source compatibility target. An actual Python 3.10 interpreter was not run. A simulated diagnostic fallback covers its lack of `BaseException.add_note`.

## Expected fixture behavior

This table describes the contract to verify, not a new observed result:

| Fixture | Result | Released evidence |
|---|---|---|
| `supported` | `sources_found` | Invented permitted support-hours excerpt and provenance |
| `insufficient` | `no_evidence` | None |
| `untrusted` | `blocked` | None |
| `restricted` | `blocked` | None |

Every result must have `generated_answer: null` and zero provider calls. No LLM is run. The deterministic fixture clock is not a live audit time. Captured files in `examples/` should come from the actual corrected CLI, not manually written illustrative answers.

## Historical source and artifact review

During initial extraction, the original NESTRA directory was read only. A private before/after comparison found **1,240 file metadata entries unchanged**, and **all four allowlisted source-file SHA-256 hashes unchanged**. The metadata comparison excluded `.git` and symlink directories; only the four selected files received content hashes. This was not a full content audit of every original file. Git was not run. This documentation correction does not repeat that original-source comparison.

The corrected stage's bounded inventory contains exactly 22 selected files after removal of the translated README variant. It includes no `.git`, `.env`, `.nestra`, caches, logs, private review evidence or personal absolute paths. Private test logs and source metadata stay outside the showcase.

## Historical test-harness repair

The first 20-test run reported 17 passes and three cleanup errors: Windows denied removal of sandbox-managed temporary directories after CLI subprocess checks. The denied cleanup was not retried. Future scratch was placed inside the explicitly writable workspace and removed only when empty.

A later repair prevents cleanup exceptions from replacing a preceding subprocess or assertion failure. Scratch handling preserves the primary failure, reports cleanup failures distinctly, tolerates an already absent directory, and retains unexpected output while failing the test. It uses no recursive deletion, permission change, retry or fallback to system Temp. Scratch creation uses the workspace `tests` directory; residual `.cli-check-*` directories are excluded by `.gitignore`.

Regression subtests simulated cleanup denial, a primary subprocess failure, an absent directory and unexpected output without accessing old denied paths. Historical read-only checks of those exact paths returned `FileNotFoundError`; no deletion was attempted, and the checks did not establish who removed them or what another sandbox session could see.

After this repair, both reviewers observed the earlier 23-test suite pass, text/JSON samples match and no new scratch directories remain. Source metadata and selected hashes also remained unchanged then. None of these historical checks authorizes retrying a denied operation.

## Scope and release boundary

The full upstream release suite and repository-wide CI success are not claimed. Standalone checks validate only this extracted showcase. Lexical overlap does not establish semantic entailment; fixture trust/sensitivity are author-assigned labels. No model-quality, token-saving or production-security result is claimed.

This documentation correction performs no package installation, API call, server start, publication, upload or repository-permission change. Release operations follow the user's authorized workflow and require review of the exact selected files, rights/attribution and current captured output. See [limitations](LIMITATIONS.md).
