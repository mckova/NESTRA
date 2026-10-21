# NESTRA

[Python 3.10+](https://www.python.org/) · [CI](https://github.com/mckova/NESTRA/actions/workflows/ci.yml) · [MIT license](LICENSE)

**Nature-inspired Evidence Selection, Trust-aware Routing Architecture.**

NESTRA is a Python control layer for evidence-based applications. It compiles local project memory, retrieves evidence with provenance, applies trust/sensitivity rules, and selects retrieval or generation routes through an SDK, CLI or HTTP gateway.

It decides what evidence may be used and when generation is needed. Routes have different evidence/output budgets and can escalate after failed checks. Routing does not optimize live prices or guarantee factual correctness.

```text
Application -> Project memory / optional retriever -> Policy + routing
                                                   |-> Blocked
                                                   |-> Retrieval: evidence only
                                                   `-> Generation tier -> checks
                                                       -> result / escalation / needs_review
```

Use it inside an API, RAG pipeline or agent; no agent framework is required.

[Hebrew](README.he.md) · [Architecture](docs/architecture.md) · [API](docs/api.md) · [CLI](docs/cli.md) · [Evaluation](docs/evaluation.md) · [Security](SECURITY.md)

## Start with local retrieval

Python 3.10+ is the supported target. There are no third-party runtime dependencies. From a checkout, install the package into your chosen Python environment:

```bash
python -m pip install -e .
```

Save this invented input as `narkis-documents.json`:

```json
[{
  "id": "support-hours",
  "title": "Support hours",
  "text": "Team Narkis support hours are Monday through Thursday from 18:00 to 21:00.",
  "trust": "trusted",
  "sourceUri": "fixture://narkis/support-hours"
}]
```

```bash
nestra ingest --store .nestra-demo --project narkis-demo --file narkis-documents.json --trust trusted
nestra route --store .nestra-demo --project narkis-demo --question "Show the evidence sources for team Narkis support hours" --mode retrieval
nestra query --store .nestra-demo --project narkis-demo --question "Show the evidence sources for team Narkis support hours" --mode retrieval
```

Inspect the plan before querying: this seeded example should show `route: retrieval` and `providerRequired: false` and needs no model key. It writes local project memory; retrieval returns evidence, not an LLM answer. The distribution is `nestra-ai`; the import is `nestra`.

The same path is available through the SDK:

```python
from nestra import FileProjectStore, NestraRuntime

runtime = NestraRuntime(store=FileProjectStore(".nestra-demo"))
runtime.ingest(
    project_id="narkis-demo",
    documents=[{
        "id": "support-hours",
        "title": "Support hours",
        "text": "Team Narkis support hours are Monday through Thursday from 18:00 to 21:00.",
        "trust": "trusted",
        "sourceUri": "fixture://narkis/support-hours",
    }],
)
question = "Show the evidence sources for team Narkis support hours"
plan = runtime.plan(project_id="narkis-demo", question=question, mode="retrieval")
assert plan["route"] == "retrieval" and plan["providerRequired"] is False
result = runtime.query(project_id="narkis-demo", question=question, mode="retrieval")
print(result)
```

Source URIs are metadata; `trusted` is application-assigned, not proof of authenticity. See the [SDK example](examples/sdk/quickstart.py), [memory guide](docs/memory.md) and [retriever adapter](examples/retrievers/vector_adapter.py).

The [offline showcase](examples/showcase/README.md) demonstrates retrieval, abstention and trust/sensitivity decisions over invented English procedures. Its isolated subset needs only Python, uses no network or LLM, and does not exercise full runtime routing.

## Routing and generation

| Route | Provider work | Purpose |
|---|---|---|
| `blocked` | No model call | Policy prevents use of the selected evidence. |
| `retrieval` | No model call | Return selected facts and provenance without generation. |
| `micro` | Up to one invocation at this stage | Compact evidence and a short-answer contract. |
| `meso` | Up to one invocation, possibly after Micro | Wider evidence and schema-constrained synthesis. |
| `full` | Up to one invocation, possibly after earlier routes | Broader eligible evidence and the configured Full model. |

Escalation can invoke multiple stages. The reference provider may retry HTTP requests, with up to two HTTP attempts per invocation by default. Telemetry records successful provider returns and reported usage, not all failures, retries or billing. Failed Full verification returns `needs_review` by default.

`verified` is a route-specific acceptance flag, not independent verification of truth. Generation checks include confidence, citations and length, with additional lexical/span heuristics for Micro; they do not establish semantic support. Retrieval has no query-topic coverage gate: applications must evaluate candidate relevance. With no eligible evidence, `mode="retrieval"` can fall through to generation; it is not a universal no-network switch. An optional external retriever may also use the network during planning.

Micro's 50–100 total API-token band is an experimental target, not a per-query promise.

### Provider boundary

The runtime is designed around a backend-agnostic provider contract, with provider-specific adapters. This repository includes an **OpenAI Responses API** reference adapter. Another backend requires a compatible implementation and response/usage mapping; arbitrary backends are not bundled.

Generation with the reference adapter requires a model-provider credential:

```python
import os
from nestra import create_openai_responses_provider

runtime.provider = create_openai_responses_provider(
    api_key=os.environ["OPENAI_API_KEY"],
)
```

Route model IDs are configurable through provider-specific [defaults](src/nestra/config.py). Route names describe request contracts, not universal model sizes or quality. Model availability, compatibility and price depend on the provider; see the [API](docs/api.md) and [adapter](src/nestra/providers.py).

## HTTP gateway and host adapters

The standard-library gateway exposes ingestion, planning, queries, project inspection, health and metrics:

```bash
export NESTRA_API_TOKEN="replace-with-a-long-random-gateway-secret"
nestra serve --store .nestra-demo --host 127.0.0.1 --port 8787
```

```bash
curl http://127.0.0.1:8787/v1/query \
  -H "Authorization: Bearer $NESTRA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"projectId":"narkis-demo","question":"Show the evidence sources for team Narkis support hours","mode":"retrieval"}'
```

These commands use POSIX shell syntax. Keep credentials outside documents and source control.

| Item | Meaning |
|---|---|
| Local retrieval | No model credential for the seeded example |
| `NESTRA_API_TOKEN` | Gateway bearer credential, required by default; `GET /health` is public |
| `OPENAI_API_KEY` | Model-provider credential for reference-adapter generation |
| Model-usage tokens | Input/output accounting units, not credentials |

The gateway credential is a shared secret you choose for your service. See [OpenAPI](openapi/nestra.openapi.yaml), the [gateway guide](docs/gateway.md) and Docker/Compose configuration. Bearer authentication does not provide tenant-level authorization or project isolation.

User-level templates are included for Claude Code, Codex and Gemini CLI:

```bash
nestra integrations status
nestra integrations install --dry-run
nestra integrations install
```

Adapters invoke the local executable; host-model calls and tokens remain separate. Compatibility depends on host versions and command/skill formats; templates do not establish broad host verification. See the [CLI guide](docs/cli.md). For control before generation, integrate the SDK or gateway before your application's model call.

## Security and observability

Controls include trust/sensitivity checks, pattern-based evidence injection detection, project-ID validation and guarded snapshot storage. The gateway adds bearer authentication, declared-body-length limits and security headers; rate/concurrency controls apply to queries, not every endpoint or incoming connection. Results expose routes, citations, guard outcomes, usage and latency. Built-in audit events omit raw prompt/evidence text but retain numeric usage counts. Project snapshots persist full document text in plaintext; audit filtering is not encrypted storage.

Applications must control trust labels and evaluate relevance. Finite injection patterns are not comprehensive protection. Tenant isolation, filesystem/network permissions, secret management and custom logging remain deployment responsibilities. Review the [security guide](docs/security-and-observability.md), [threat model](docs/threat-model.md) and [reporting policy](SECURITY.md).

## Experimental learning and evaluation

The optional local Logistic Regression router estimates Micro suitability from numeric features, without provider calls or raw text in feature records. Policy rules control blocked/retrieval decisions and can veto recommendations. See the [guide](docs/learned-router.md), [SDK example](examples/sdk/learned_router.py) and [holdout](benchmarks/router-ml/results/HOLDOUT_REPORT.md).

The bundled artifact is **experimental**, with Micro disabled: calibration could not satisfy minimum precision/support requirements (0.90 precision and three selections). Its six-case holdout has no positive Micro-safe labels and establishes no savings.

A [historical 12-question experiment](benchmarks/nestra-oracle/results/REPORT.md), generated on 2026-08-05 with an earlier implementation, reported Direct at 73.6 mean tokens/F1 0.576, Micro-100 at 87.6/F1 0.686, and Adaptive at 1,416/F1 0.842. This small tradeoff study does not establish current runtime performance or factual accuracy. The [evaluation policy](docs/evaluation.md) explains offline and live evaluation boundaries.

Offline evaluation entry points, which may write local result artifacts:

```bash
python benchmarks/project_memory_offline/run.py
python scripts/train_router.py
python benchmarks/router_ml/run.py
```

Live oracle evaluation downloads data and calls models, requiring credentials/network and potentially incurring charges; read its [instructions](benchmarks/nestra-oracle/README.md) first. Reports are historical evidence, not current test results. Check [Actions](https://github.com/mckova/NESTRA/actions) for the commit you use.

## Project map and development

| Path | Contents |
|---|---|
| `src/nestra/` | Runtime, project memory, routing, guards, storage, providers, CLI and gateway |
| `src/nestra/ml/` | Feature extraction, Logistic Regression, calibration and policy vetoes |
| `tests/` | Runtime, storage, security, CLI, HTTP, provider and ML tests |
| `benchmarks/` | Offline and live evaluation tools and reports |
| `schemas/`, `openapi/` | Configuration, model and public API contracts |
| `models/router/` | Versioned experimental router artifact |
| `examples/` | SDK/retriever examples and the isolated offline showcase |

For development, install the optional tools and run the repository checks:

```bash
python -m pip install -e ".[dev]"
python -m pytest
python scripts/validate_release.py
```

See [contributing](CONTRIBUTING.md), [conduct](CODE_OF_CONDUCT.md), [support](SUPPORT.md), [roadmap](ROADMAP.md) and [changelog](CHANGELOG.md). NESTRA and Agent Hive are separate; see their [history](docs/cross-pollination.md).

## License

Licensed under [MIT](LICENSE). The existing copyright notice, **Copyright (c) 2026 Agent Hive Contributors**, is retained; documentation changes do not reassign ownership.
