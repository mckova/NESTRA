# NESTRA

[![CI](https://github.com/mckova/NESTRA/actions/workflows/ci.yml/badge.svg)](https://github.com/mckova/NESTRA/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Nature-inspired Evidence Selection, Trust-aware Routing Architecture.**

NESTRA is a trust-aware adaptive inference layer for Python. It sits between an application and its retrieval/model stack, compiles project memory locally, and routes each request to the least expensive path that still passes deterministic accuracy checks.

```text
Client -> NESTRA -> Blocked | Retrieval (0 model tokens) | Micro | Meso | Full -> Guard -> Response
```

NESTRA is not an agent framework. An application, API, RAG pipeline, or agent may use it, but no agent is required. Retrieval can complete a request without generation; compact generation is accepted only when evidence and output checks pass; uncertain work escalates instead of silently exchanging accuracy for cost.

[עברית](README.he.md) · [Architecture](docs/architecture.md) · [Python API](docs/api.md) · [CLI](docs/cli.md) · [Learned router](docs/learned-router.md) · [Evaluation](docs/evaluation.md) · [Security](SECURITY.md)

## Offline showcase

Try the [standalone showcase](examples/showcase/README.md) for deterministic source retrieval, abstention, and trust/sensitivity decisions over invented procedures. It requires only an existing Python interpreter, uses no network or API key, and does not generate LLM answers.

```bash
cd examples/showcase
python -I -B demo.py
python -I -B run_checks.py
```

## Why it is different

| Route | Model calls | Decision |
|---|---:|---|
| `blocked` | 0 | Relevant evidence violates trust, sensitivity, or injection policy. |
| `retrieval` | 0 | Ranked facts and provenance already satisfy the request. |
| `micro` | 1 | Two compact evidence atoms plus a short-answer contract; target 50–100 total API tokens. |
| `meso` | 1, or 2 after Micro | A wider evidence chain and schema-constrained synthesis. |
| `full` | 1, or final escalation | The strongest configured model and broader trusted evidence. |

The 50–100 token band is an experimental Micro target, not a promise for every question. If the accuracy guard fails, NESTRA escalates or returns `needs_review`.

The optional local Logistic Regression router predicts when Micro may be safe using 15 numeric routing features. It spends zero provider tokens and stores no raw question or evidence text. Deterministic rules still own Blocked/Retrieval decisions, trust, sensitivity, prompt-injection defense, evidence eligibility, and answer verification.

## Install from this checkout

NESTRA requires Python 3.10+ and has no runtime dependencies.

```bash
git clone https://github.com/mckova/NESTRA.git
cd NESTRA
python -m pip install -e ".[dev]"
python -m pytest
python scripts/validate_release.py
```

The distribution name is `nestra-ai`; the import package is `nestra`. The repository is ready to build as a wheel and source distribution, but does not claim that a PyPI release already exists.

## Native AI CLI command

Install the engine from GitHub with `pipx`, then install NESTRA's user-level adapters:

```bash
pipx install git+https://github.com/mckova/NESTRA.git
nestra integrations install
```

This makes `/nestra` available in Claude Code and Gemini CLI. Codex uses the current Agent Skills syntax: invoke `$nestra`, or open `/skills` and choose NESTRA. Inspect without changing files with `nestra integrations status` or `nestra integrations install --dry-run`. Existing modified commands are never overwritten unless `--force` is supplied; forced updates create timestamped backups.

The adapters are deliberately thin: they ask the host AI CLI to call the local `nestra` executable and surface its evidence, verification state, route, latency, and provider-token usage. They do not turn NESTRA into an agent and do not make the host CLI's own model tokens disappear. For true pre-model savings, integrate the Python runtime or HTTP gateway before the application's LLM call.

## Five-minute CLI flow

```bash
nestra ingest --project casting --file examples/project-memory/casting.json --trust trusted
nestra route --project casting --question "Show the evidence sources" --mode retrieval
nestra query --project casting --question "Show the evidence sources" --mode retrieval
```

The last command needs no API key and reports zero model calls and zero provider tokens. Generation routes use `OPENAI_API_KEY`. The provider interface is replaceable; the reference adapter uses the OpenAI Responses API.

## Python SDK

```python
from nestra import FileProjectStore, NestraRuntime

nestra = NestraRuntime(store=FileProjectStore(".nestra"))
nestra.ingest(
    project_id="apollo",
    documents=[{
        "title": "Apollo 11",
        "text": "Apollo 11 landed on the Moon in July 1969.",
        "trust": "trusted",
        "sourceUri": "https://www.nasa.gov/mission/apollo-11/",
    }],
)

result = nestra.query(
    project_id="apollo",
    question="Show the evidence sources for Apollo 11",
    mode="retrieval",
)
assert result["telemetry"]["usage"]["totalTokens"] == 0
```

To enable generation:

```python
import os
from nestra import create_openai_responses_provider

nestra.provider = create_openai_responses_provider(api_key=os.environ["OPENAI_API_KEY"])
```

See [quickstart.py](examples/sdk/quickstart.py), [learned_router.py](examples/sdk/learned_router.py), and the [vector retriever adapter](examples/retrievers/vector_adapter.py).

## HTTP gateway

```bash
export NESTRA_API_TOKEN="replace-with-a-long-random-token"
export OPENAI_API_KEY="..."  # optional for Retrieval-only
nestra serve --host 127.0.0.1 --port 8787
```

```bash
curl http://127.0.0.1:8787/v1/query \
  -H "Authorization: Bearer $NESTRA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"projectId":"casting","question":"Show the evidence sources","mode":"retrieval"}'
```

The standard-library gateway exposes health, ingestion, route planning, querying, project inspection, and aggregate metrics. See the [OpenAPI contract](openapi/nestra.openapi.yaml) and [deployment guide](docs/gateway.md). A non-root, read-only Docker/Compose deployment is included.

## Accuracy, safety, and monitoring

- External retrieval defaults to untrusted; vector similarity never implies trust.
- Sensitivity and evidence prompt-injection gates run before provider calls.
- Project IDs cannot traverse the filesystem; snapshots use atomic replacement.
- The gateway applies constant-time bearer comparison, body limits, security headers, rate limits, and concurrency limits.
- Audits omit prompts, evidence, credentials, and token values.
- Results expose selected route, citations, guard outcome, calls, latency, token categories, and alerts.
- Failed Full verification fails closed with `needs_review` by default.

NESTRA is a control layer, not a replacement for tenant isolation, a secret manager, network sandboxing, or provider-side safety controls. Read the [threat model](docs/threat-model.md).

## Honest evaluation status

The network-free suite currently passes all seven safety/routing cases with zero provider tokens. The live oracle compares direct GPT-5.6, local BM25 RAG + GPT-5.6, fixed NESTRA, adaptive NESTRA, pre-gated Micro, Micro-100, and an accuracy-locked cascade on the same seeded HotpotQA examples.

Historical 12-question results found Micro-100 averaged 87.6 tokens with token F1 0.686, while Adaptive averaged 1,416 tokens with F1 0.842. That makes Micro interesting, not proven. The bundled learned artifact is deliberately `experimental`: its small calibration set could not satisfy the required 0.90 Micro precision, so it disables Micro. The repository therefore demonstrates the complete ML pipeline without pretending that the tiny model already produces savings.

Reproduce the local evidence:

```bash
python benchmarks/project_memory_offline/run.py
python scripts/train_router.py
python benchmarks/router_ml/run.py
```

The live oracle additionally needs an API key and network access:

```bash
python -m benchmarks.nestra_oracle.benchmark --limit 12
```

See [evaluation policy](docs/evaluation.md), the [historical oracle report](benchmarks/nestra-oracle/results/REPORT.md), and the [learned-router holdout](benchmarks/router-ml/results/HOLDOUT_REPORT.md).

## Project map

- `src/nestra/` — Python runtime, memory, routing, guards, security, storage, provider, CLI, and gateway.
- `src/nestra/ml/` — feature extraction, Logistic Regression, calibration, and deterministic vetoes.
- `tests/` — unit, integration, provider, storage, CLI, HTTP, security, ML, and oracle-library tests.
- `benchmarks/` — offline and live evaluations; production code never imports them.
- `schemas/` and `openapi/` — public wire contracts.
- `models/router/` — versioned, data-only experimental model artifact.

NESTRA and **Agent Hive** are separate projects. There are no cross-project imports; the few lessons retained from their accidental overlap are documented in [cross-pollination](docs/cross-pollination.md).

## Contributing and license

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md), follow the [Code of Conduct](CODE_OF_CONDUCT.md), and run `python scripts/validate_release.py` before proposing a release. Licensed under [MIT](LICENSE).
