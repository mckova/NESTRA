"""Aggregate content-free process metrics."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable


class MetricsCollector:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = RLock()
        self.reset()

    def record(self, event: dict[str, Any]) -> None:
        with self._lock:
            self.requests += 1
            self.routes[event.get("route", "unknown")] += 1
            self.total_latency_ms += float(event.get("latencyMs", 0) or 0)
            self.total_model_calls += int(event.get("modelCalls", 0) or 0)
            self.total_tokens += int(event.get("totalTokens", 0) or 0)
            self.router_sources[event.get("routerSource", "unknown")] += 1
            if event.get("routerModelId"):
                self.router_models[event["routerModelId"]] += 1
            if event.get("routerVetoReason"):
                self.router_vetoes[event["routerVetoReason"]] += 1
            self.blocked += int(event.get("status") == "blocked")
            self.errors += int(event.get("status") == "error")
            self.verified += int(event.get("verified") is True)
            self.alerts.update(event.get("alerts", []))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            count = max(1, self.requests)
            return {
                "generatedAt": self.clock()
                .astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "requests": self.requests,
                "routes": dict(self.routes),
                "blocked": self.blocked,
                "errors": self.errors,
                "verified": self.verified,
                "averageLatencyMs": round(self.total_latency_ms / count, 2) if self.requests else 0,
                "averageModelCalls": round(self.total_model_calls / count, 2)
                if self.requests
                else 0,
                "totalTokens": self.total_tokens,
                "averageTokens": round(self.total_tokens / count, 2) if self.requests else 0,
                "routerSources": dict(self.router_sources),
                "routerModels": dict(self.router_models),
                "routerVetoes": dict(self.router_vetoes),
                "alerts": dict(self.alerts),
            }

    def reset(self) -> None:
        with self._lock:
            self.requests = self.blocked = self.errors = self.verified = 0
            self.total_latency_ms = 0.0
            self.total_model_calls = self.total_tokens = 0
            self.routes: Counter[str] = Counter()
            self.router_sources: Counter[str] = Counter()
            self.router_models: Counter[str] = Counter()
            self.router_vetoes: Counter[str] = Counter()
            self.alerts: Counter[str] = Counter()
