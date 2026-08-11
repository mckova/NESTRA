"""Validated immutable configuration for NESTRA."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

DEFAULT_NESTRA_CONFIG: dict[str, Any] = {
    "security": {
        "maxQuestionChars": 4_000,
        "maxSensitivity": 0.5,
        "maxConcurrent": 4,
        "requestsPerMinute": 60,
        "requireTrustedEvidence": True,
    },
    "routing": {
        "requireMultiDocument": True,
        "unsafeRelevance": 0.2,
        "minimumSafeCoverage": 0.2,
        "retrievalMinimumTopicCoverage": 0.5,
        "microMinimumCoverage": 0.45,
        "microMinimumIntentCoverage": 0.15,
        "microMaxEvidenceTokens": 55,
        "mesoMinimumCoverage": 0.25,
        "mesoMinimumIntentCoverage": 0.08,
        "mesoMaxEvidenceTokens": 240,
        "learnedMicroMaxEvidenceTokens": 70,
    },
    "tiers": {
        "micro": {
            "model": "gpt-5.6-luna",
            "reasoningEffort": "none",
            "maxOutputTokens": 24,
            "targetTotalTokens": 100,
        },
        "meso": {
            "model": "gpt-5.6-terra",
            "reasoningEffort": "low",
            "maxOutputTokens": 160,
            "maxTotalTokens": 500,
        },
        "full": {
            "model": "gpt-5.6-sol",
            "reasoningEffort": "medium",
            "maxOutputTokens": 512,
            "maxTotalTokens": 2_400,
        },
    },
    "runtime": {"maxModelCalls": 3, "maxLatencyMs": 30_000, "failClosedOnGuardFailure": True},
}


def create_nestra_config(overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Deep-merge overrides into defaults and validate the public contract."""
    config = _merge(DEFAULT_NESTRA_CONFIG, dict(overrides or {}))
    validate_config(config)
    return config


def validate_config(config: Mapping[str, Any]) -> None:
    if not isinstance(config, Mapping):
        raise ValueError("NESTRA config must be a mapping.")
    _reject_unknown(config, {"security", "routing", "tiers", "runtime"}, "config")
    security = _section(config, "security")
    _reject_unknown(
        security,
        {
            "maxQuestionChars",
            "maxSensitivity",
            "maxConcurrent",
            "requestsPerMinute",
            "requireTrustedEvidence",
        },
        "security",
    )
    _positive_int(security, "maxQuestionChars", "security")
    _unit_number(security, "maxSensitivity", "security")
    _positive_int(security, "maxConcurrent", "security")
    _positive_int(security, "requestsPerMinute", "security")
    _boolean(security, "requireTrustedEvidence", "security")
    if security["requireTrustedEvidence"] is not True:
        raise ValueError("security.requireTrustedEvidence cannot be disabled.")

    routing = _section(config, "routing")
    _reject_unknown(
        routing,
        {
            "requireMultiDocument",
            "unsafeRelevance",
            "minimumSafeCoverage",
            "retrievalMinimumTopicCoverage",
            "microMinimumCoverage",
            "microMinimumIntentCoverage",
            "microMaxEvidenceTokens",
            "mesoMinimumCoverage",
            "mesoMinimumIntentCoverage",
            "mesoMaxEvidenceTokens",
            "learnedMicroMaxEvidenceTokens",
        },
        "routing",
    )
    _boolean(routing, "requireMultiDocument", "routing")
    for key in (
        "unsafeRelevance",
        "minimumSafeCoverage",
        "retrievalMinimumTopicCoverage",
        "microMinimumCoverage",
        "microMinimumIntentCoverage",
        "mesoMinimumCoverage",
        "mesoMinimumIntentCoverage",
    ):
        _unit_number(routing, key, "routing")
    for key in ("microMaxEvidenceTokens", "mesoMaxEvidenceTokens", "learnedMicroMaxEvidenceTokens"):
        _positive_int(routing, key, "routing")

    tiers = _section(config, "tiers")
    _reject_unknown(tiers, {"micro", "meso", "full"}, "tiers")
    for tier in ("micro", "meso", "full"):
        row = tiers.get(tier)
        if (
            not isinstance(row, Mapping)
            or not isinstance(row.get("model"), str)
            or not row["model"].strip()
        ):
            raise ValueError(f"tiers.{tier}.model is required.")
        allowed = {"model", "reasoningEffort", "maxOutputTokens"}
        allowed.add("targetTotalTokens" if tier == "micro" else "maxTotalTokens")
        _reject_unknown(row, allowed, f"tiers.{tier}")
        if row.get("reasoningEffort") not in {"none", "low", "medium", "high", "xhigh", "max"}:
            raise ValueError(f"tiers.{tier}.reasoningEffort is invalid.")
        if (
            isinstance(row.get("maxOutputTokens"), bool)
            or not isinstance(row.get("maxOutputTokens"), int)
            or row["maxOutputTokens"] < 1
        ):
            raise ValueError(f"tiers.{tier}.maxOutputTokens must be positive.")
    target = tiers["micro"].get("targetTotalTokens")
    if isinstance(target, bool) or not isinstance(target, int) or not 50 <= target <= 100:
        raise ValueError(
            "tiers.micro.targetTotalTokens must remain within the 50-100 research band."
        )
    for tier in ("meso", "full"):
        _positive_int(tiers[tier], "maxTotalTokens", f"tiers.{tier}")

    runtime = _section(config, "runtime")
    _reject_unknown(
        runtime,
        {"maxModelCalls", "maxLatencyMs", "failClosedOnGuardFailure"},
        "runtime",
    )
    _positive_int(runtime, "maxModelCalls", "runtime")
    _positive_int(runtime, "maxLatencyMs", "runtime")
    _boolean(runtime, "failClosedOnGuardFailure", "runtime")


def _merge(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    output = deepcopy(dict(left))
    for key, value in right.items():
        if isinstance(value, Mapping) and isinstance(output.get(key), Mapping):
            output[key] = _merge(output[key], value)
        else:
            output[key] = deepcopy(value)
    return output


def _section(config: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = config.get(name)
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping.")
    return value


def _reject_unknown(config: Mapping[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(config) - allowed)
    if unknown:
        raise ValueError(f"{name} contains unsupported keys: {', '.join(unknown)}.")


def _positive_int(config: Mapping[str, Any], key: str, section: str) -> None:
    value = config.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{section}.{key} must be a positive integer.")


def _unit_number(config: Mapping[str, Any], key: str, section: str) -> None:
    value = config.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError(f"{section}.{key} must be between 0 and 1.")


def _boolean(config: Mapping[str, Any], key: str, section: str) -> None:
    if not isinstance(config.get(key), bool):
        raise ValueError(f"{section}.{key} must be a boolean.")
