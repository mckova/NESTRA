# Python API

Public symbols are exported from `nestra`. Python 3.10+ is supported; the runtime uses only the standard library.

## `NestraRuntime`

```python
runtime = NestraRuntime(
    store=store,
    provider=provider,
    retriever=retriever,
    retriever_default_trust="untrusted",
    router_model=router_model,
    config=config,
    hooks=hooks,
    metrics=metrics,
    rate_limiter=rate_limiter,
)
```

`store` is required. `provider` is required only when a request selects Micro, Meso, or Full. `retriever` is optional; persisted Project Memory is used when it is absent. `router_model` may be a parsed artifact or `LearnedRouterModel`; omitting it preserves deterministic routing.

### Ingest

```python
runtime.ingest(project_id="apollo", documents=documents, default_trust="trusted")
```

Documents support `id`, `title`, `text`, `sentences`, `sourceUri`, `trust`, `sensitivity`, and `sourceQuality`. Missing trust is untrusted unless the caller deliberately supplies a trusted default.

### Plan without a model call

```python
plan = runtime.plan(project_id="apollo", question="...", mode="auto")
```

Planning performs retrieval, security checks, and routing. It returns route reasons, safe evidence, estimated evidence tokens, provider requirement, and router provenance. Learned-router inference is a local dot product and sigmoid, not a provider call.

### Execute the guarded cascade

```python
result = runtime.query(
    project_id="apollo",
    question="...",
    mode="auto",
    actor_id="user-42",
)
```

`mode` is `auto` or `retrieval`. Results conform to `schemas/query-result.schema.json` and include evidence, verification state, usage categories, attempted routes, model calls, latency, and alerts.

### Telemetry

```python
snapshot = runtime.telemetry()
```

Returns aggregate metrics and redacted hook events for the current process.

## Model provider contract

```python
class MyProvider:
    name = "my-provider"

    def generate(self, request: dict) -> dict:
        return {
            "id": "response-id",
            "model": request["model"],
            "text": "...",
            "parsed": None,
            "latencyMs": 42,
            "usage": {
                "inputTokens": 20,
                "outputTokens": 5,
                "reasoningTokens": 0,
                "totalTokens": 25,
                "cachedInputTokens": 0,
            },
        }
```

The request contains `name`, `instructions`, `input`, `model`, `reasoningEffort`, `maxOutputTokens`, and optional `outputSchema`. A provider should enforce the schema where supported and return `parsed`. Exceptions must never include credentials.

The reference `OpenAIResponsesProvider` is dependency-free and sends `store: false`, explicit reasoning effort, bounded retry, timeouts, structured-output schemas, and normalized usage to the Responses API.

## Retriever contract

```python
class MyRetriever:
    def retrieve(self, *, project_id: str, query: str, limit: int = 24) -> dict:
        return {"documents": [{
            "id": "doc-1",
            "title": "Title",
            "text": "Retrieved content",
            "sourceUri": "https://example.test/source",
            "trust": "trusted",
            "sensitivity": 0,
            "sourceQuality": 0.93,
        }]}
```

Only return `trust: "trusted"` after independently validating source and tenant boundaries. A similarity score becomes `sourceQuality`; it never implies trust.

## Other public components

- `FileProjectStore`: atomic `save`, `load`, `inspect`, `list`, `delete`, and redacted `audit` operations.
- `create_openai_responses_provider`: reference Responses API adapter.
- `create_nestra_config`: validated deep merge of configuration.
- `HookBus`, `MetricsCollector`, and `SlidingWindowRateLimiter`: operational extension points.
- `ScopedMemory`, `GoalController`, and topology helpers: deterministic memory/control primitives.
- `LearnedRouterModel`, `train_micro_safety_router`, `evaluate_router_model`, `extract_router_features`, and `apply_learned_routing`: optional local ML pipeline.

Wire JSON intentionally retains camelCase for language-neutral HTTP/schema compatibility; Python call sites use snake_case.
