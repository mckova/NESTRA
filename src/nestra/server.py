"""Authenticated standard-library HTTP gateway."""

from __future__ import annotations

import hmac
import json
import math
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import unquote, urlparse

from .security import NestraRateLimitError, SlidingWindowRateLimiter
from .storage import ProjectNotFoundError
from .version import VERSION


def create_nestra_server(
    *,
    runtime: object,
    host: str = "127.0.0.1",
    port: int = 8787,
    token: str | None = None,
    allow_unauthenticated: bool = False,
    max_body_bytes: int = 1_000_000,
    rate_limiter: SlidingWindowRateLimiter | None = None,
    max_workers: int | None = None,
    request_timeout_seconds: float | None = None,
) -> ThreadingHTTPServer:
    if runtime is None:
        raise ValueError("create_nestra_server requires a runtime.")
    if not token and not allow_unauthenticated:
        raise ValueError("NESTRA_API_TOKEN is required unless allow_unauthenticated is enabled.")
    if allow_unauthenticated and host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("Unauthenticated mode is restricted to a loopback host.")
    if (
        isinstance(max_body_bytes, bool)
        or not isinstance(max_body_bytes, int)
        or max_body_bytes < 1
    ):
        raise ValueError("max_body_bytes must be a positive integer.")
    configured_workers = (
        getattr(runtime, "config", {}).get("security", {}).get("maxConcurrent", 4)
        if max_workers is None
        else max_workers
    )
    if (
        isinstance(configured_workers, bool)
        or not isinstance(configured_workers, int)
        or configured_workers < 1
    ):
        raise ValueError("max_workers must be a positive integer.")
    configured_timeout = (
        getattr(runtime, "config", {}).get("runtime", {}).get("maxLatencyMs", 30_000) / 1_000
        if request_timeout_seconds is None
        else request_timeout_seconds
    )
    if (
        isinstance(configured_timeout, bool)
        or not isinstance(configured_timeout, (int, float))
        or not math.isfinite(float(configured_timeout))
        or configured_timeout <= 0
    ):
        raise ValueError("request_timeout_seconds must be positive.")
    gateway_limiter = rate_limiter or getattr(runtime, "rate_limiter", None)
    if gateway_limiter is None:
        limit = getattr(runtime, "config", {}).get("security", {}).get("requestsPerMinute", 60)
        gateway_limiter = SlidingWindowRateLimiter(limit=limit)

    class Handler(BaseHTTPRequestHandler):
        server_version = "NESTRA/2"

        def do_GET(self) -> None:  # noqa: N802
            self._dispatch()

        def do_POST(self) -> None:  # noqa: N802
            self._dispatch()

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _dispatch(self) -> None:
            try:
                path = urlparse(self.path).path
                if self.command == "GET" and path == "/health":
                    return self._json(
                        200, {"status": "ok", "service": "nestra", "version": VERSION}
                    )
                if path.startswith("/v1/"):
                    rate = gateway_limiter.consume(self.client_address[0])
                    if not rate["allowed"]:
                        raise NestraRateLimitError(int(rate["retryAfterMs"]))
                if token and not self._authorized(token):
                    return self._json(
                        401,
                        {"error": {"code": "unauthorized", "message": "Bearer token required."}},
                    )
                if self.command == "GET" and path == "/v1/metrics":
                    return self._json(200, runtime.telemetry()["metrics"])
                if self.command == "GET" and path == "/v1/projects":
                    return self._json(200, {"projects": runtime.store.list()})
                if (
                    self.command == "GET"
                    and path.startswith("/v1/projects/")
                    and path.count("/") == 3
                ):
                    return self._json(200, runtime.store.inspect(unquote(path.rsplit("/", 1)[1])))
                if (
                    self.command == "POST"
                    and path.startswith("/v1/projects/")
                    and path.endswith("/ingest")
                ):
                    project_id = unquote(path[len("/v1/projects/") : -len("/ingest")].strip("/"))
                    body = self._body(max_body_bytes)
                    result = runtime.ingest(
                        project_id=project_id,
                        documents=body.get("documents"),
                        default_trust=body.get("defaultTrust"),
                    )
                    return self._json(
                        201, {"projectId": result["projectId"], "stats": result["stats"]}
                    )
                if self.command == "POST" and path == "/v1/route":
                    body = self._body(max_body_bytes)
                    return self._json(
                        200,
                        runtime.plan(
                            project_id=body.get("projectId"),
                            question=body.get("question"),
                            mode=body.get("mode", "auto"),
                        ),
                    )
                if self.command == "POST" and path == "/v1/query":
                    body = self._body(max_body_bytes)
                    return self._json(
                        200,
                        runtime.query(
                            project_id=body.get("projectId"),
                            question=body.get("question"),
                            mode=body.get("mode", "auto"),
                            actor_id=self.client_address[0],
                            enforce_rate_limit=False,
                        ),
                    )
                return self._json(
                    404, {"error": {"code": "not_found", "message": "Route not found."}}
                )
            except Exception as error:
                status, code = _status(error)
                headers = (
                    {"Retry-After": str(max(1, round(error.retry_after_ms / 1_000)))}
                    if isinstance(error, NestraRateLimitError)
                    else None
                )
                return self._json(
                    status,
                    {
                        "error": {
                            "code": code,
                            "message": str(error)
                            if status < 500 or getattr(error, "code", None)
                            else "Internal server error.",
                        }
                    },
                    headers,
                )

        def _authorized(self, expected: str) -> bool:
            header = self.headers.get("Authorization", "")
            return header.startswith("Bearer ") and hmac.compare_digest(
                header[7:].encode(), expected.encode()
            )

        def _body(self, maximum: int) -> dict[str, Any]:
            if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
                error = ValueError("Content-Type must be application/json.")
                error.code = "unsupported_media_type"
                raise error
            if self.headers.get("Transfer-Encoding"):
                error = ValueError("Transfer-Encoding is not supported.")
                error.code = "unsupported_transfer_encoding"
                raise error
            lengths = self.headers.get_all("Content-Length") or []
            if len(lengths) > 1:
                error = ValueError("Multiple Content-Length headers are not allowed.")
                error.code = "invalid_content_length"
                raise error
            raw_length = self.headers.get("Content-Length", "0") or "0"
            try:
                length = int(raw_length)
            except ValueError as cause:
                error = ValueError("Content-Length must be a non-negative integer.")
                error.code = "invalid_content_length"
                raise error from cause
            if length < 0:
                error = ValueError("Content-Length must be a non-negative integer.")
                error.code = "invalid_content_length"
                raise error
            if length > maximum:
                error = ValueError("Request body is too large.")
                error.code = "payload_too_large"
                raise error
            try:
                parsed = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError) as cause:
                error = ValueError("Request body must contain valid JSON.")
                error.code = "invalid_json"
                raise error from cause
            if not isinstance(parsed, dict):
                raise ValueError("Request body must be a JSON object.")
            return parsed

        def _json(
            self, status: int, body: dict[str, Any], headers: dict[str, str] | None = None
        ) -> None:
            payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
            )
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(payload)

    return _BoundedThreadingHTTPServer(
        (host, int(port)),
        Handler,
        max_workers=int(configured_workers),
        request_timeout_seconds=float(configured_timeout),
    )


class _BoundedThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler: type,
        *,
        max_workers: int,
        request_timeout_seconds: float,
    ):
        self._worker_slots = threading.BoundedSemaphore(max_workers)
        self._request_timeout_seconds = request_timeout_seconds
        super().__init__(server_address, handler)

    def get_request(self) -> tuple[Any, Any]:
        request, client_address = super().get_request()
        request.settimeout(self._request_timeout_seconds)
        return request, client_address

    def process_request(self, request: Any, client_address: Any) -> None:
        self._worker_slots.acquire()
        try:
            super().process_request(request, client_address)
        except Exception:
            self._worker_slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._worker_slots.release()


def _status(error: Exception) -> tuple[int, str]:
    code = getattr(error, "code", "internal_error")
    if isinstance(error, ProjectNotFoundError):
        return 404, "project_not_found"
    if code == "unsupported_media_type":
        return 415, code
    if code == "payload_too_large":
        return 413, code
    if code == "rate_limited":
        return 429, code
    if code == "concurrency_limited":
        return 503, code
    if str(code).startswith("provider_"):
        return 502, code
    if isinstance(error, (ValueError, TypeError)):
        return 400, code if code != "internal_error" else "invalid_request"
    return 500, code
