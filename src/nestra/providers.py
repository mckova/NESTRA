"""Provider-neutral model contract and a standard-library OpenAI Responses adapter."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable


class ModelProviderError(RuntimeError):
    def __init__(
        self, message: str, *, code: str = "provider_error", status: int | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


def assert_model_provider(provider: object) -> None:
    if provider is None or not callable(getattr(provider, "generate", None)):
        raise ModelProviderError(
            "A model provider is required for this route.", code="provider_required"
        )


def normalize_usage(value: dict[str, Any] | None) -> dict[str, int]:
    row = value or {}
    input_tokens = _integer(row.get("inputTokens", row.get("input_tokens", 0)))
    output_tokens = _integer(row.get("outputTokens", row.get("output_tokens", 0)))
    reasoning = _integer(
        row.get(
            "reasoningTokens",
            row.get(
                "reasoning_tokens", row.get("output_tokens_details", {}).get("reasoning_tokens", 0)
            ),
        )
    )
    cached = _integer(
        row.get(
            "cachedInputTokens",
            row.get("cached_tokens", row.get("input_tokens_details", {}).get("cached_tokens", 0)),
        )
    )
    total = _integer(row.get("totalTokens", row.get("total_tokens", input_tokens + output_tokens)))
    return {
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "reasoningTokens": reasoning,
        "totalTokens": total,
        "cachedInputTokens": cached,
    }


class OpenAIResponsesProvider:
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        endpoint: str = "https://api.openai.com/v1/responses",
        timeout_seconds: float = 30,
        max_retries: int = 1,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self.api_key = str(
            api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY") or ""
        ).strip()
        if not self.api_key:
            raise ModelProviderError("OPENAI_API_KEY is required.", code="provider_key_missing")
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, int(max_retries))
        self.opener = opener or urllib.request.urlopen

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": request["model"],
            "instructions": request.get("instructions", ""),
            "input": request.get("input", ""),
            "max_output_tokens": request.get("maxOutputTokens", 256),
            "store": False,
        }
        effort = request.get("reasoningEffort")
        if effort and effort != "none":
            body["reasoning"] = {"effort": effort}
        if request.get("outputSchema"):
            schema = request["outputSchema"]
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": schema.get("name", "nestra_output"),
                    "strict": schema.get("strict", True),
                    "schema": schema["schema"],
                }
            }
        payload = json.dumps(body).encode("utf-8")
        started = time.perf_counter()
        for attempt in range(self.max_retries + 1):
            http_request = urllib.request.Request(
                self.endpoint,
                data=payload,
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            try:
                with self.opener(http_request, timeout=self.timeout_seconds) as response:
                    result = json.loads(response.read().decode("utf-8"))
                text = _extract_output(result)
                parsed = None
                if request.get("outputSchema"):
                    try:
                        parsed = json.loads(text)
                    except json.JSONDecodeError:
                        parsed = None
                return {
                    "id": result.get("id"),
                    "model": result.get("model", request["model"]),
                    "text": text,
                    "parsed": parsed,
                    "latencyMs": round((time.perf_counter() - started) * 1000, 2),
                    "usage": normalize_usage(result.get("usage")),
                }
            except urllib.error.HTTPError as error:
                status = error.code
                if status in {408, 409, 429, 500, 502, 503, 504} and attempt < self.max_retries:
                    time.sleep(0.1 * (2**attempt))
                    continue
                raise ModelProviderError(
                    f"OpenAI request failed with status {status}.",
                    code="provider_http_error",
                    status=status,
                ) from error
            except (urllib.error.URLError, TimeoutError) as error:
                if attempt < self.max_retries:
                    time.sleep(0.1 * (2**attempt))
                    continue
                raise ModelProviderError(
                    "OpenAI request failed.", code="provider_network_error"
                ) from error
        raise ModelProviderError("OpenAI request failed.")


def create_openai_responses_provider(**options: Any) -> OpenAIResponsesProvider:
    return OpenAIResponsesProvider(**options)


def _extract_output(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"].strip()
    parts = []
    for output in payload.get("output", []):
        for content in output.get("content", []):
            if isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "\n".join(parts).strip()


def _integer(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
