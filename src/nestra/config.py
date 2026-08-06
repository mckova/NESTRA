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
    tiers = config.get("tiers")
    for tier in ("micro", "meso", "full"):
        row = tiers.get(tier) if isinstance(tiers, Mapping) else None
        if not isinstance(row, Mapping) or not str(row.get("model", "")).strip():
            raise ValueError(f"tiers.{tier}.model is required.")
        if not isinstance(row.get("maxOutputTokens"), int) or row["maxOutputTokens"] < 1:
            raise ValueError(f"tiers.{tier}.maxOutputTokens must be positive.")
    target = tiers["micro"].get("targetTotalTokens")
    if not isinstance(target, int) or not 50 <= target <= 100:
        raise ValueError(
            "tiers.micro.targetTotalTokens must remain within the 50-100 research band."
        )
    security = config.get("security", {})
    if not isinstance(security.get("maxConcurrent"), int) or security["maxConcurrent"] < 1:
        raise ValueError("security.maxConcurrent must be positive.")


def _merge(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    output = deepcopy(dict(left))
    for key, value in right.items():
        if isinstance(value, Mapping) and isinstance(output.get(key), Mapping):
            output[key] = _merge(output[key], value)
        else:
            output[key] = deepcopy(value)
    return output
