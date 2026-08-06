"""Production NESTRA runtime and guarded escalation cascade."""

from __future__ import annotations

import json
import threading
import time
import uuid
from copy import deepcopy
from typing import Any

from .config import create_nestra_config
from .control import HookBus
from .evidence import (
    compile_atomic_evidence,
    evaluate_accuracy_lock,
    ground_answer_span,
    micro_prompt,
)
from .metrics import MetricsCollector
from .ml.features import extract_router_features
from .ml.hybrid import apply_learned_routing
from .ml.logistic import LearnedRouterModel
from .project_memory import compile_project_memory
from .providers import assert_model_provider, normalize_usage
from .retrievers import normalize_retrieved_documents
from .routing import route_nestra_query
from .security import (
    NestraRateLimitError,
    SlidingWindowRateLimiter,
    detect_prompt_injection,
    sanitize_user_text,
    stable_hash,
    validate_project_id,
)
from .storage import FileProjectStore

ANSWER_SCHEMA = {
    "name": "nestra_grounded_answer",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["answer", "confidence", "evidence_ids"],
        "additionalProperties": False,
    },
}


class NestraRuntime:
    def __init__(
        self,
        *,
        store: FileProjectStore,
        provider: object | None = None,
        retriever: object | None = None,
        retriever_default_trust: str = "untrusted",
        router_model: LearnedRouterModel | dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
        hooks: HookBus | None = None,
        metrics: MetricsCollector | None = None,
        rate_limiter: SlidingWindowRateLimiter | None = None,
    ) -> None:
        if store is None:
            raise ValueError("NestraRuntime requires a project store.")
        self.store = store
        self.provider = provider
        self.retriever = retriever
        self.retriever_default_trust = retriever_default_trust
        self.learned_router = (
            router_model
            if isinstance(router_model, LearnedRouterModel)
            else LearnedRouterModel(router_model)
            if router_model
            else None
        )
        self.config = create_nestra_config(config)
        self.hooks = hooks or HookBus()
        self.metrics = metrics or MetricsCollector()
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter(
            limit=self.config["security"]["requestsPerMinute"]
        )
        self._capacity = threading.BoundedSemaphore(self.config["security"]["maxConcurrent"])

    def ingest(
        self,
        *,
        project_id: str,
        documents: list[dict[str, Any]],
        default_trust: str | None = None,
        clock: Any = None,
    ) -> dict[str, Any]:
        project_id = validate_project_id(project_id)
        index = compile_project_memory(
            {"projectId": project_id, "documents": documents},
            clock=clock,
            default_trust=default_trust or "untrusted",
        )
        saved = self.store.save(index)
        self.hooks.emit("project_ingested", {"projectId": project_id, "stats": saved["stats"]})
        return {**saved, "snapshot": index.export()}

    def plan(self, *, project_id: str, question: str, mode: str = "auto") -> dict[str, Any]:
        prepared = self._prepare(project_id=project_id, question=question, mode=mode)
        recall = self._evidence_for_route(prepared)
        return {
            "projectId": prepared["projectId"],
            "route": prepared["routing"]["route"],
            "authorized": prepared["routing"]["authorized"],
            "reasons": prepared["routing"]["reasons"],
            "evidence": self._retrieval_evidence(prepared["expandedRecall"])
            if prepared["routing"]["route"] == "retrieval"
            else self._public_evidence(recall),
            "estimatedEvidenceTokens": recall.get("estimatedEvidenceTokens", 0),
            "providerRequired": prepared["routing"]["route"] not in {"blocked", "retrieval"},
            "router": deepcopy(prepared["routing"]["router"]),
        }

    def query(
        self, *, project_id: str, question: str, mode: str = "auto", actor_id: str = "anonymous"
    ) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        started = time.perf_counter()
        rate = self.rate_limiter.consume(actor_id)
        if not rate["allowed"]:
            raise NestraRateLimitError(int(rate["retryAfterMs"]))
        if not self._capacity.acquire(blocking=False):
            error = RuntimeError("NESTRA concurrency limit reached.")
            error.code = "concurrency_limited"
            raise error
        calls: list[dict[str, Any]] = []
        attempted: list[str] = []
        alerts: list[str] = []
        final_route = "blocked"
        prepared: dict[str, Any] | None = None
        try:
            prepared = self._prepare(project_id=project_id, question=question, mode=mode)
            self.hooks.emit(
                "before_query",
                {
                    "requestId": request_id,
                    "projectId": prepared["projectId"],
                    "questionHash": stable_hash(prepared["question"]),
                },
            )
            self.hooks.emit(
                "after_route",
                {
                    "requestId": request_id,
                    "route": prepared["routing"]["route"],
                    "reasons": prepared["routing"]["reasons"],
                },
            )
            final_route = prepared["routing"]["route"]
            if final_route == "blocked":
                return self._finish(
                    self._result(
                        request_id,
                        prepared,
                        "blocked",
                        "blocked",
                        None,
                        False,
                        [],
                        None,
                        calls,
                        ["blocked"],
                        alerts,
                        started,
                    )
                )
            if final_route == "retrieval":
                attempted.append("retrieval")
                return self._finish(
                    self._result(
                        request_id,
                        prepared,
                        "retrieval",
                        "completed",
                        None,
                        True,
                        self._retrieval_evidence(prepared["expandedRecall"]),
                        None,
                        calls,
                        attempted,
                        alerts,
                        started,
                    )
                )
            assert_model_provider(self.provider)
            outcome = None
            if final_route == "micro":
                attempted.append("micro")
                outcome = self._run_micro(prepared, calls)
                if outcome["accepted"]:
                    if (
                        self._usage(calls)["totalTokens"]
                        > self.config["tiers"]["micro"]["targetTotalTokens"]
                    ):
                        alerts.append("micro_token_target_exceeded")
                    return self._finish(
                        self._result(
                            request_id,
                            prepared,
                            "micro",
                            "completed",
                            outcome["answer"],
                            True,
                            outcome["evidence"],
                            outcome["guard"],
                            calls,
                            attempted,
                            alerts,
                            started,
                        )
                    )
                alerts.append("micro_guard_escalation")
                self.hooks.emit(
                    "guard_failed",
                    {
                        "requestId": request_id,
                        "route": "micro",
                        "reasons": outcome["guard"]["reasons"],
                    },
                )
            if len(calls) < self.config["runtime"]["maxModelCalls"] and final_route != "full":
                attempted.append("meso")
                final_route = "meso"
                outcome = self._run_structured(
                    "meso", prepared["expandedRecall"], prepared["question"], calls
                )
                if outcome["accepted"]:
                    return self._finish(
                        self._result(
                            request_id,
                            prepared,
                            "meso",
                            "completed",
                            outcome["answer"],
                            True,
                            outcome["evidence"],
                            outcome["guard"],
                            calls,
                            attempted,
                            alerts,
                            started,
                        )
                    )
                alerts.append("meso_guard_escalation")
                self.hooks.emit(
                    "guard_failed",
                    {
                        "requestId": request_id,
                        "route": "meso",
                        "reasons": outcome["guard"]["reasons"],
                    },
                )
            attempted.append("full")
            final_route = "full"
            if len(calls) >= self.config["runtime"]["maxModelCalls"]:
                return self._finish(
                    self._result(
                        request_id,
                        prepared,
                        "full",
                        "needs_review",
                        None,
                        False,
                        self._public_evidence(prepared["expandedRecall"]),
                        None,
                        calls,
                        attempted,
                        [*alerts, "model_call_budget_exhausted"],
                        started,
                    )
                )
            full_recall = prepared["index"].recall(
                prepared["question"],
                trusted_only=True,
                max_sensitivity=self.config["security"]["maxSensitivity"],
                limit=24,
                max_atoms=12,
            )
            if not full_recall["atoms"]:
                return self._finish(
                    self._result(
                        request_id,
                        prepared,
                        "full",
                        "needs_review",
                        None,
                        False,
                        [],
                        None,
                        calls,
                        attempted,
                        [*alerts, "insufficient_trusted_evidence"],
                        started,
                    )
                )
            outcome = self._run_structured("full", full_recall, prepared["question"], calls)
            accepted = outcome["accepted"]
            answer = (
                outcome["answer"]
                if accepted or not self.config["runtime"]["failClosedOnGuardFailure"]
                else None
            )
            return self._finish(
                self._result(
                    request_id,
                    prepared,
                    "full",
                    "completed" if accepted else "needs_review",
                    answer,
                    accepted,
                    outcome["evidence"],
                    outcome["guard"],
                    calls,
                    attempted,
                    alerts if accepted else [*alerts, "full_guard_failed"],
                    started,
                )
            )
        except Exception as error:
            latency = round((time.perf_counter() - started) * 1000, 2)
            self.metrics.record(
                {
                    "route": final_route,
                    "status": "error",
                    "latencyMs": latency,
                    "modelCalls": len(calls),
                    "totalTokens": self._usage(calls)["totalTokens"],
                    "alerts": alerts,
                }
            )
            self.store.audit(
                {
                    "type": "query.error",
                    "requestId": request_id,
                    "route": final_route,
                    "code": getattr(error, "code", "error"),
                    "latencyMs": latency,
                }
            )
            raise
        finally:
            self._capacity.release()

    def telemetry(self) -> dict[str, Any]:
        return {"metrics": self.metrics.snapshot(), "events": self.hooks.trace()}

    def _prepare(self, *, project_id: str, question: str, mode: str) -> dict[str, Any]:
        project_id = validate_project_id(project_id)
        question = sanitize_user_text(
            question, field="question", max_chars=self.config["security"]["maxQuestionChars"]
        )
        index = self.store.load(project_id)
        if self.retriever:
            result = self.retriever.retrieve(project_id=project_id, query=question, limit=24)
            documents = normalize_retrieved_documents(
                result, default_trust=self.retriever_default_trust
            )
            if documents:
                index = compile_project_memory(
                    {"projectId": project_id, "documents": documents},
                    default_trust=self.retriever_default_trust,
                )
        maximum = self.config["security"]["maxSensitivity"]
        raw = index.recall(question, trusted_only=False, max_sensitivity=1, limit=12, max_atoms=6)
        safe = index.recall(
            question, trusted_only=True, max_sensitivity=maximum, limit=12, max_atoms=2
        )
        expanded = index.recall(
            question, trusted_only=True, max_sensitivity=maximum, limit=16, max_atoms=6
        )
        deterministic = route_nestra_query(
            question=question,
            mode=mode,
            raw_recall=raw,
            safe_recall=safe,
            expanded_recall=expanded,
            options={**self.config["routing"], "maxSensitivity": maximum},
        )
        features = extract_router_features(
            question=question, safe_recall=safe, expanded_recall=expanded
        )
        if self.learned_router:
            routing = apply_learned_routing(
                deterministic_routing=deterministic,
                model=self.learned_router,
                features=features,
                safe_recall=safe,
                expanded_recall=expanded,
                options={**self.config["routing"], "maxSensitivity": maximum},
            )
        else:
            routing = {
                **deterministic,
                "router": {
                    "source": "deterministic",
                    "deterministicRoute": deterministic["route"],
                    "selectedRoute": deterministic["route"],
                    "vetoReason": None,
                },
            }
        return {
            "projectId": project_id,
            "question": question,
            "index": index,
            "rawRecall": raw,
            "safeRecall": safe,
            "expandedRecall": expanded,
            "routing": routing,
            "routerFeatures": features,
        }

    def _run_micro(self, prepared: dict[str, Any], calls: list[dict[str, Any]]) -> dict[str, Any]:
        documents = [
            row
            for row in prepared["index"].export()["documents"]
            if row["trust"] == "trusted"
            and row["sensitivity"] <= self.config["security"]["maxSensitivity"]
        ]
        tier = self.config["tiers"]["micro"]
        compilation = compile_atomic_evidence(
            prepared["question"],
            documents,
            target_total_tokens=tier["targetTotalTokens"],
            max_output_tokens=tier["maxOutputTokens"],
        )
        flags = list(
            dict.fromkeys(
                flag
                for atom in compilation["atoms"]
                for flag in detect_prompt_injection(atom["text"])["flags"]
            )
        )
        if flags:
            guard = {"accepted": False, "reasons": ["prompt_injection_in_evidence", *flags]}
            return {"accepted": False, "answer": None, "evidence": [], "guard": guard}
        response = self._call_provider(
            "micro",
            {
                "name": "nestra_micro",
                "instructions": "Use only E. Return only the shortest answer span. Return unknown if E is insufficient.",
                "input": micro_prompt(prepared["question"], compilation),
                "maxOutputTokens": tier["maxOutputTokens"],
                "model": tier["model"],
                "reasoningEffort": tier["reasoningEffort"],
            },
            calls,
        )
        answer = ground_answer_span(response.get("text"), compilation["evidenceText"])
        guard = evaluate_accuracy_lock(prepared["question"], answer, compilation)
        sources = {row["title"]: row.get("sourceUri") for row in documents}
        evidence = [
            {**atom, "sourceUri": sources.get(atom["title"])} for atom in compilation["atoms"]
        ]
        return {
            "accepted": guard["accepted"],
            "answer": answer,
            "guard": guard,
            "evidence": evidence,
        }

    def _run_structured(
        self, tier_name: str, recall: dict[str, Any], question: str, calls: list[dict[str, Any]]
    ) -> dict[str, Any]:
        tier = self.config["tiers"][tier_name]
        evidence_text = "\n".join(f"{atom['id']}:{atom['promptText']}" for atom in recall["atoms"])
        response = self._call_provider(
            tier_name,
            {
                "name": f"nestra_{tier_name}",
                "instructions": "Answer only from the supplied evidence. Cite evidence_ids used. If evidence is insufficient, answer unknown with confidence 0.",
                "input": f"Q:{question}\nE:\n{evidence_text}",
                "maxOutputTokens": tier["maxOutputTokens"],
                "model": tier["model"],
                "reasoningEffort": tier["reasoningEffort"],
                "outputSchema": ANSWER_SCHEMA,
            },
            calls,
        )
        parsed = response.get("parsed")
        if not isinstance(parsed, dict):
            try:
                parsed = json.loads(response.get("text", "{}"))
            except json.JSONDecodeError:
                parsed = {}
        guard = self._validate_structured(parsed, recall, tier_name)
        if (
            tier.get("maxTotalTokens")
            and self._usage(calls)["totalTokens"] > tier["maxTotalTokens"]
        ):
            guard["reasons"].append("cascade_token_budget_exceeded")
            guard["accepted"] = False
        return {
            "accepted": guard["accepted"],
            "answer": str(parsed.get("answer", "")).strip() or None,
            "guard": guard,
            "evidence": self._public_evidence(recall, parsed.get("evidence_ids")),
        }

    def _call_provider(
        self, route: str, request: dict[str, Any], calls: list[dict[str, Any]]
    ) -> dict[str, Any]:
        self.hooks.emit(
            "before_model_call",
            {
                "route": route,
                "model": request["model"],
                "maxOutputTokens": request["maxOutputTokens"],
            },
        )
        response = self.provider.generate(request)
        usage = normalize_usage(response.get("usage"))
        call = {
            "route": route,
            "provider": getattr(self.provider, "name", "custom"),
            "model": response.get("model", request["model"]),
            "latencyMs": float(response.get("latencyMs", 0)),
            "usage": usage,
        }
        calls.append(call)
        self.hooks.emit("after_model_call", call)
        return {**response, "usage": usage}

    def _validate_structured(
        self, parsed: dict[str, Any], recall: dict[str, Any], tier: str
    ) -> dict[str, Any]:
        reasons = []
        answer = str(parsed.get("answer", "")).strip()
        confidence = parsed.get("confidence")
        ids = list(
            dict.fromkeys(
                parsed.get("evidence_ids", [])
                if isinstance(parsed.get("evidence_ids"), list)
                else []
            )
        )
        atoms = {row["id"]: row for row in recall["atoms"]}
        if not answer or answer.lower() == "unknown":
            reasons.append("empty_or_unknown")
        if not isinstance(confidence, (int, float)) or confidence < (
            0.55 if tier == "full" else 0.65
        ):
            reasons.append("low_confidence")
        if not ids:
            reasons.append("missing_citations")
        if any(item not in atoms for item in ids):
            reasons.append("invalid_citation")
        documents = {atoms[item]["documentId"] for item in ids if item in atoms}
        if tier == "meso" and recall.get("structuralChain") and len(documents) < 2:
            reasons.append("single_document_support")
        if len(answer) > 4_000:
            reasons.append("answer_too_long")
        return {
            "accepted": not reasons,
            "reasons": reasons,
            "confidence": float(confidence) if isinstance(confidence, (int, float)) else 0,
            "evidenceIds": ids,
        }

    def _result(
        self,
        request_id: str,
        prepared: dict[str, Any],
        route: str,
        status: str,
        answer: str | None,
        verified: bool,
        evidence: list[dict[str, Any]],
        guard: dict[str, Any] | None,
        calls: list[dict[str, Any]],
        attempted: list[str],
        alerts: list[str],
        started: float,
    ) -> dict[str, Any]:
        latency = round((time.perf_counter() - started) * 1000, 2)
        if latency > self.config["runtime"]["maxLatencyMs"]:
            alerts = [*alerts, "runtime_latency_budget_exceeded"]
        return {
            "schemaVersion": 1,
            "requestId": request_id,
            "projectId": prepared["projectId"],
            "route": route,
            "status": status,
            "answer": answer,
            "verified": verified,
            "router": deepcopy(prepared["routing"]["router"]),
            "reasons": prepared["routing"]["reasons"],
            "evidence": evidence,
            "guard": guard,
            "telemetry": {
                "attemptedRoutes": attempted,
                "modelCalls": len(calls),
                "calls": calls,
                "usage": self._usage(calls),
                "latencyMs": latency,
                "alerts": list(dict.fromkeys(alerts)),
            },
        }

    def _finish(self, result: dict[str, Any]) -> dict[str, Any]:
        event = {
            "route": result["route"],
            "status": result["status"],
            "verified": result["verified"],
            "routerSource": result["router"]["source"],
            "routerModelId": result["router"].get("modelId"),
            "routerVetoReason": result["router"].get("vetoReason"),
            "latencyMs": result["telemetry"]["latencyMs"],
            "modelCalls": result["telemetry"]["modelCalls"],
            "totalTokens": result["telemetry"]["usage"]["totalTokens"],
            "alerts": result["telemetry"]["alerts"],
        }
        self.metrics.record(event)
        self.hooks.emit(
            "after_query",
            {
                "requestId": result["requestId"],
                "projectId": result["projectId"],
                "route": result["route"],
                "status": result["status"],
                "usage": result["telemetry"]["usage"],
            },
        )
        self.store.audit(
            {
                "type": "query.completed",
                "requestId": result["requestId"],
                "projectId": result["projectId"],
                **event,
            }
        )
        return result

    @staticmethod
    def _usage(calls: list[dict[str, Any]]) -> dict[str, int]:
        keys = (
            "inputTokens",
            "outputTokens",
            "reasoningTokens",
            "totalTokens",
            "cachedInputTokens",
        )
        return {key: sum(call["usage"][key] for call in calls) for key in keys}

    @staticmethod
    def _public_evidence(
        recall: dict[str, Any], selected_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        selected = set(selected_ids) if selected_ids else None
        return [
            {
                "id": atom["id"],
                "title": atom["title"],
                "text": atom["text"],
                "documentId": atom["documentId"],
                "sourceUri": atom.get("provenance", {}).get("sourceUri"),
                "retrievalScore": atom.get("retrievalScore"),
                "provenance": atom.get("provenance", {}),
            }
            for atom in recall.get("atoms", [])
            if selected is None or atom["id"] in selected
        ]

    @classmethod
    def _retrieval_evidence(cls, recall: dict[str, Any]) -> list[dict[str, Any]]:
        positive = [atom for atom in recall.get("atoms", []) if atom.get("retrievalScore", 0) > 0]
        return cls._public_evidence({"atoms": positive or recall.get("atoms", [])[:2]})

    @staticmethod
    def _evidence_for_route(prepared: dict[str, Any]) -> dict[str, Any]:
        return (
            prepared["safeRecall"]
            if prepared["routing"]["route"] == "micro"
            else prepared["expandedRecall"]
        )
