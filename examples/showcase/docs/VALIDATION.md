# Local validation — 2026-10-21

## Recorded result

On Windows, using the existing Python **3.13.12** interpreter, the integration reviewer ran:

```powershell
python -I -B run_checks.py
```

**23 tests passed; exit code 0.** The independent test agent also completed the same 23-test suite successfully. Python 3.10+ is the source compatibility target, but this task exercised only 3.13.12.

The checked contracts include:

- Verbatim copied-file hashes, preserved attribution, and standard-library/local imports only.
- Snapshot integrity, mutation isolation and project-identifier validation.
- Real fixture provenance, unsupported/near-topic/title-only abstention, and repeatable output.
- Untrusted and sensitivity-restricted source content, identifiers, titles and references absent from returned output.
- Detected source/question instruction patterns blocked; invalid policy numbers rejected.
- Network, environment reads and file I/O denied by runtime test patches during evaluation.
- CLI JSON identical across fresh isolated processes; one-case selection works; an invalid case exits unsuccessfully without a traceback. CLI scratch directories stay empty.

The runtime patches exercise evaluation after imports. They are scoped checks, not an operating-system network sandbox or proof about every possible upstream configuration. The application code was also inspected before execution. It imports no network client, provider adapter or process launcher.

## Actual CLI examples

Both files in `examples/` were captured from the actual CLI, not written as illustrative answers:

```powershell
python -I -B demo.py
python -I -B demo.py --json
```

| Fixture | Result | Released evidence |
|---|---|---|
| `supported` | `sources_found` | Invented permitted support-hours excerpt and provenance |
| `insufficient` | `no_evidence` | None |
| `untrusted` | `blocked` | None |
| `restricted` | `blocked` | None |

All four results have `generated_answer: null` and zero provider calls. No LLM was run. The deterministic fixture clock is not a live audit time.

## Original source and artifact boundary

The original NESTRA directory was read only. A private before/after comparison found **1,240 file metadata entries unchanged**, and **all four allowlisted source-file SHA-256 hashes unchanged**. The metadata comparison excludes `.git` and symlink directories; only the four selected files received content hashes. This is not a full content audit of every original file. Git was not run.

The deliverable contains only the explicit source subset, new wrapper, synthetic fixtures, tests, documentation and captured fixture output. A bounded file inventory found no copied `.git`, `.env`, `.nestra`, caches, logs or personal absolute paths. No private source-review evidence belongs in this showcase. The test logs and source metadata are kept in a separate private sibling directory.

## Initial test-harness issue

The first 20-test run reported 17 passes and three cleanup errors: Windows denied removal of sandbox-managed temporary directories after CLI subprocess checks. The denied cleanup was not retried. Future test scratch was placed inside the explicitly writable workspace and removed only when empty. The final 23-test suite passed with that harness. Private execution notes retain the denied targets; these paths are unrelated to the original source.

### Follow-up repair

The remaining harness issue was that an exception in the cleanup `finally` block could replace a preceding subprocess or assertion failure. Scratch handling now preserves the primary failure, reports cleanup failures distinctly, tolerates a directory already absent during cleanup, and retains unexpected CLI output while still failing the test. There is no recursive deletion, permission change, retry or fallback to system Temp. Scratch creation uses the explicit workspace `tests` directory; residual `.cli-check-*` directories are excluded by `.gitignore`.

Regression subtests simulate cleanup denial, a primary subprocess failure, an absent directory and unexpected output without accessing the old denied paths. Read-only checks of the three exact historical paths returned `FileNotFoundError` in the current session. No deletion was attempted; the checks do not establish who removed those paths or what another sandbox session can see.

After the repair, the independent test agent and integration reviewer each reran all **23 tests successfully**. The reviewer also reran both text and JSON demos: both exited with code 0, matched the existing captured examples exactly, and reported zero provider calls. No new `.cli-check-*` directories remained. The source metadata and four selected hashes were rechecked and remained unchanged. A simulated diagnostic fallback covers Python 3.10's lack of `BaseException.add_note`; an actual Python 3.10 interpreter was not run.

## Existing-repository integration checks

For inclusion under `examples/showcase`, the newly authored launchers, wrapper and tests were aligned with the existing repository's Ruff formatting/import rules. The copied core and license remain byte-identical to `PROVENANCE.json`. The 23-test suite passed again in the staged directory. Both staged CLI modes matched the captured examples. Repository-wide pytest and release validation are separate from this standalone suite and are run by the existing GitHub CI; no CI success is inferred from these local results.

The local Ruff checks passed using the repository's selected rules and Python target:

```powershell
python -I -B -m ruff format --check --isolated --no-cache --line-length 100 --target-version py310 examples/showcase
python -I -B -m ruff check --isolated --no-cache --select E4,E7,E9,F,I --target-version py310 examples/showcase
```

## Scope of the recorded checks

The full upstream release suite was not run or claimed. These checks validate only this extracted showcase. Lexical overlap does not establish semantic entailment; fixture trust/sensitivity are author-assigned labels. No model-quality, token-saving or production-security result is claimed.

No packages were installed and no API, server, publication, upload or repository-permission change was performed. Before a public release, review the exact release files and rights/attribution, confirm that only this showcase is included, rerun checks on that selection, and obtain the user's separate publication decision. See [limitations](LIMITATIONS.md).
