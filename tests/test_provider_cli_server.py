from __future__ import annotations

import io
import json
import re
import socket
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

import nestra.cli as cli_module
from nestra import (
    FileProjectStore,
    ModelProviderError,
    NestraRuntime,
    OpenAIResponsesProvider,
    SlidingWindowRateLimiter,
    create_nestra_config,
    create_nestra_server,
    normalize_usage,
    validate_config,
    validate_project_id,
)
from nestra.cli import run_cli


def _documents():
    return [
        {"title": "Alpha", "text": "Alpha links to Beta.", "trust": "trusted"},
        {"title": "Beta", "text": "Beta is located in Jerusalem.", "trust": "trusted"},
    ]


def test_usage_normalization_covers_reasoning_and_cache():
    usage = normalize_usage(
        {
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "input_tokens_details": {"cached_tokens": 3},
            "output_tokens_details": {"reasoning_tokens": 2},
        }
    )
    assert usage == {
        "inputTokens": 10,
        "outputTokens": 5,
        "reasoningTokens": 2,
        "totalTokens": 15,
        "cachedInputTokens": 3,
    }
    assert (
        normalize_usage(
            {
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 1,
                "input_tokens_details": None,
                "output_tokens_details": None,
            }
        )["totalTokens"]
        == 15
    )


@pytest.mark.parametrize(
    "config",
    [
        {"tiers": {"micro": {"model": ""}}},
        {"tiers": {"meso": {"maxOutputTokens": 0}}},
        {"tiers": {"meso": {"maxOutputTokens": True}}},
        {"tiers": {"full": {"model": {"name": "not-a-string"}}}},
        {"tiers": {"micro": {"targetTotalTokens": 101}}},
        {"tiers": {"micro": {"targetTotalTokens": True}}},
        {"security": {"maxConcurrent": 0}},
        {"security": {"maxQuestionChars": 0}},
        {"security": {"requireTrustedEvidence": False}},
        {"routing": {"microMinimumCoverage": 1.1}},
        {"runtime": {"maxModelCalls": 0}},
        {"runtime": {"unknown": True}},
        {"tiers": {"meso": {"maxTotalTokens": 0}}},
    ],
)
def test_invalid_configurations_fail_closed(config):
    with pytest.raises(ValueError):
        create_nestra_config(config)
    with pytest.raises(ValueError):
        validate_config(None)


def test_provider_requires_a_key_and_normalizes_invalid_counts(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_KEY", raising=False)
    with pytest.raises(ModelProviderError, match="OPENAI_API_KEY"):
        OpenAIResponsesProvider()
    monkeypatch.setenv("OPENAI_API_KEY", "real-process-secret")
    with pytest.raises(ModelProviderError, match="OPENAI_API_KEY"):
        OpenAIResponsesProvider(use_environment=False)
    with pytest.raises(ModelProviderError, match="HTTPS"):
        OpenAIResponsesProvider(api_key="test", endpoint="http://provider.example/v1")
    with pytest.raises(ModelProviderError, match="HTTPS"):
        OpenAIResponsesProvider(api_key="test", endpoint="https://")
    with pytest.raises(ModelProviderError, match="timeout"):
        OpenAIResponsesProvider(api_key="test", timeout_seconds=0)
    assert OpenAIResponsesProvider(
        api_key="test", endpoint="http://127.0.0.1:8080/v1"
    ).endpoint.startswith("http://127.0.0.1")
    assert normalize_usage({"input_tokens": "invalid", "output_tokens": -3})["totalTokens"] == 0


def test_openai_adapter_sends_reasoning_schema_and_store_false():
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {
                    "id": "r1",
                    "model": "test",
                    "output_text": '{"answer":"ok"}',
                    "usage": {"input_tokens": 2, "output_tokens": 1, "total_tokens": 3},
                }
            ).encode()

    def opener(request, timeout):
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return Response()

    provider = OpenAIResponsesProvider(api_key="test-key", opener=opener)
    result = provider.generate(
        {
            "model": "test",
            "instructions": "ground",
            "input": "Q",
            "maxOutputTokens": 10,
            "reasoningEffort": "low",
            "outputSchema": {"name": "answer", "schema": {"type": "object"}},
        }
    )
    assert captured["body"]["store"] is False
    assert captured["body"]["reasoning"] == {"effort": "low"}
    assert captured["body"]["text"]["format"]["type"] == "json_schema"
    assert result["parsed"] == {"answer": "ok"}


def test_openai_adapter_extracts_nested_text_and_handles_invalid_structured_json():
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {
                    "model": "test",
                    "output": [{"content": [{"text": "not-json"}]}],
                    "usage": {},
                }
            ).encode()

    provider = OpenAIResponsesProvider(
        api_key="test-key", opener=lambda *_args, **_kwargs: Response()
    )
    result = provider.generate(
        {
            "model": "test",
            "reasoningEffort": "none",
            "outputSchema": {"schema": {"type": "object"}},
        }
    )
    assert result["text"] == "not-json"
    assert result["parsed"] is None


def test_server_configuration_fails_closed(tmp_path: Path):
    runtime = NestraRuntime(store=FileProjectStore(tmp_path))
    with pytest.raises(ValueError, match="requires a runtime"):
        create_nestra_server(runtime=None, token="secret")
    with pytest.raises(ValueError, match="NESTRA_API_TOKEN"):
        create_nestra_server(runtime=runtime)
    with pytest.raises(ValueError, match="loopback"):
        create_nestra_server(runtime=runtime, host="0.0.0.0", allow_unauthenticated=True)
    with pytest.raises(ValueError, match="max_workers"):
        create_nestra_server(runtime=runtime, token="secret", max_workers=0)
    with pytest.raises(ValueError, match="request_timeout_seconds"):
        create_nestra_server(runtime=runtime, token="secret", request_timeout_seconds=0)


def test_cli_ingests_and_routes_without_api_key(tmp_path: Path):
    source = tmp_path / "documents.json"
    source.write_text(json.dumps({"documents": _documents()}), encoding="utf-8")
    out, err = io.StringIO(), io.StringIO()
    assert (
        run_cli(
            [
                "ingest",
                "--store",
                str(tmp_path / "store"),
                "--project",
                "demo",
                "--file",
                str(source),
            ],
            env={},
            stdout=out,
            stderr=err,
        )
        == 0
    )
    out = io.StringIO()
    assert (
        run_cli(
            [
                "route",
                "--store",
                str(tmp_path / "store"),
                "--project",
                "demo",
                "--question",
                "Show the evidence sources",
                "--mode",
                "retrieval",
            ],
            env={},
            stdout=out,
            stderr=err,
        )
        == 0
    )
    assert json.loads(out.getvalue())["route"] == "retrieval"
    assert err.getvalue() == ""


def test_cli_rejects_invalid_router_artifact(tmp_path: Path):
    artifact = tmp_path / "bad.json"
    artifact.write_text('{"kind":"bad"}', encoding="utf-8")
    err = io.StringIO()
    code = run_cli(
        [
            "route",
            "--store",
            str(tmp_path),
            "--project",
            "demo",
            "--question",
            "hello",
            "--router-model",
            str(artifact),
        ],
        env={},
        stdout=io.StringIO(),
        stderr=err,
    )
    assert code == 1
    assert "Unsupported learned router artifact" in err.getvalue()


def test_cli_empty_environment_does_not_fall_back_to_process_secrets(monkeypatch):
    captured = {}

    class Runtime:
        store = object()
        provider = None

        @staticmethod
        def plan(**_kwargs):
            return {"providerRequired": True}

        @staticmethod
        def query(**_kwargs):
            return {"status": "ok"}

    def provider_factory(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setenv("OPENAI_API_KEY", "qa-secret-that-must-not-be-read")
    monkeypatch.setattr(cli_module, "create_openai_responses_provider", provider_factory)
    assert (
        run_cli(
            ["query", "--project", "demo", "--question", "question"],
            env={},
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            runtime=Runtime(),
        )
        == 0
    )
    assert captured["api_key"] is None
    assert captured["use_environment"] is False


def test_http_gateway_health_auth_and_zero_token_retrieval(tmp_path: Path):
    runtime = NestraRuntime(store=FileProjectStore(tmp_path))
    runtime.ingest(project_id="demo", documents=_documents())
    server = create_nestra_server(runtime=runtime, host="127.0.0.1", port=0, token="server-secret")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        health = json.loads(urllib.request.urlopen(f"{base}/health").read())
        assert health["version"] == "2.1.1"
        try:
            urllib.request.urlopen(f"{base}/v1/projects")
        except urllib.error.HTTPError as error:
            assert error.code == 401
        request = urllib.request.Request(
            f"{base}/v1/query",
            data=json.dumps(
                {"projectId": "demo", "question": "Show the evidence sources", "mode": "retrieval"}
            ).encode(),
            method="POST",
            headers={"Authorization": "Bearer server-secret", "Content-Type": "application/json"},
        )
        result = json.loads(urllib.request.urlopen(request).read())
        assert result["route"] == "retrieval" and result["telemetry"]["usage"]["totalTokens"] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_gateway_rejects_negative_content_length(tmp_path: Path):
    runtime = NestraRuntime(store=FileProjectStore(tmp_path))
    server = create_nestra_server(
        runtime=runtime,
        host="127.0.0.1",
        port=0,
        allow_unauthenticated=True,
        max_body_bytes=10,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    body = json.dumps(
        {"projectId": "demo", "question": "body larger than ten bytes", "mode": "auto"}
    ).encode()
    client = socket.create_connection(("127.0.0.1", server.server_port), timeout=3)
    try:
        client.sendall(
            b"POST /v1/route HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: -1\r\n"
            b"Connection: close\r\n\r\n" + body
        )
        client.shutdown(socket.SHUT_WR)
        response = b""
        while chunk := client.recv(4096):
            response += chunk
        assert response.split(b" ", 2)[1] == b"400"
        assert b"invalid_content_length" in response
    finally:
        client.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_gateway_rate_limit_covers_non_query_endpoints(tmp_path: Path):
    runtime = NestraRuntime(store=FileProjectStore(tmp_path))
    runtime.ingest(project_id="demo", documents=_documents())
    limiter = SlidingWindowRateLimiter(limit=1, window_ms=60_000)
    server = create_nestra_server(
        runtime=runtime,
        host="127.0.0.1",
        port=0,
        token="server-secret",
        rate_limiter=limiter,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        route = urllib.request.Request(
            f"{base}/v1/route",
            data=json.dumps(
                {"projectId": "demo", "question": "Show the evidence sources", "mode": "retrieval"}
            ).encode(),
            method="POST",
            headers={"Authorization": "Bearer server-secret", "Content-Type": "application/json"},
        )
        assert urllib.request.urlopen(route).status == 200
        projects = urllib.request.Request(
            f"{base}/v1/projects", headers={"Authorization": "Bearer server-secret"}
        )
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(projects)
        assert caught.value.code == 429
        assert urllib.request.urlopen(f"{base}/health").status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize(
    "options",
    [
        {"max_body_bytes": 1.5},
        {"max_body_bytes": True},
        {"max_workers": 1.5},
        {"request_timeout_seconds": float("nan")},
    ],
)
def test_gateway_limits_require_strict_numeric_types(tmp_path: Path, options):
    runtime = NestraRuntime(store=FileProjectStore(tmp_path))
    with pytest.raises(ValueError):
        create_nestra_server(
            runtime=runtime,
            host="127.0.0.1",
            port=0,
            allow_unauthenticated=True,
            **options,
        )


def test_public_schemas_match_runtime_validation():
    root = Path(__file__).resolve().parents[1]
    config = create_nestra_config()
    schema = json.loads((root / "schemas" / "nestra-config.schema.json").read_text())
    assert list(Draft202012Validator(schema).iter_errors(config)) == []
    invalid = json.loads(json.dumps(config))
    invalid["security"]["maxConcurrent"] = 0
    assert list(Draft202012Validator(schema).iter_errors(invalid))
    with pytest.raises(ValueError, match="maxConcurrent"):
        validate_config(invalid)

    openapi = yaml.safe_load((root / "openapi" / "nestra.openapi.yaml").read_text())
    pattern = openapi["components"]["schemas"]["ProjectId"]["pattern"]
    assert re.fullmatch(pattern, "valid-project")
    assert not re.fullmatch(pattern, "invalid-")
    with pytest.raises(ValueError):
        validate_project_id("invalid-")
    for path in ("/v1/projects", "/v1/metrics"):
        responses = openapi["paths"][path]["get"]["responses"]
        assert "401" in responses and "429" in responses
    assert openapi["paths"]["/v1/metrics"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/Metrics"}
