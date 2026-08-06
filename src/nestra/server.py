"""Authenticated standard-library HTTP gateway."""

from __future__ import annotations

import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import unquote, urlparse

from .security import NestraRateLimitError
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
) -> ThreadingHTTPServer:
    if runtime is None:
        raise ValueError("create_nestra_server requires a runtime.")
    if not token and not allow_unauthenticated:
        raise ValueError("NESTRA_API_TOKEN is required unless allow_unauthenticated is enabled.")
    if allow_unauthenticated and host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("Unauthenticated mode is restricted to a loopback host.")

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
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length > maximum:
                error = ValueError("Request body is too large.")
                error.code = "payload_too_large"
                raise error
            try:
                return json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except json.JSONDecodeError as cause:
                error = ValueError("Request body must contain valid JSON.")
                error.code = "invalid_json"
                raise error from cause

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

    return ThreadingHTTPServer((host, int(port)), Handler)


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
