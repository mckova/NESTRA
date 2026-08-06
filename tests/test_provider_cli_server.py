from __future__ import annotations

import io
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from nestra import (
    FileProjectStore,
    ModelProviderError,
    NestraRuntime,
    OpenAIResponsesProvider,
    create_nestra_config,
    create_nestra_server,
    normalize_usage,
    validate_config,
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


@pytest.mark.parametrize(
    "config",
    [
        {"tiers": {"micro": {"model": ""}}},
        {"tiers": {"meso": {"maxOutputTokens": 0}}},
        {"tiers": {"micro": {"targetTotalTokens": 101}}},
        {"security": {"maxConcurrent": 0}},
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


def test_http_gateway_health_auth_and_zero_token_retrieval(tmp_path: Path):
    runtime = NestraRuntime(store=FileProjectStore(tmp_path))
    runtime.ingest(project_id="demo", documents=_documents())
    server = create_nestra_server(runtime=runtime, host="127.0.0.1", port=0, token="server-secret")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        health = json.loads(urllib.request.urlopen(f"{base}/health").read())
        assert health["version"] == "2.1.0"
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
