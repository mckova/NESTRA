"""Hybrid learned routing with deterministic hard-policy and eligibility vetoes."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .features import extract_router_features
from .logistic import LearnedRouterModel


def apply_learned_routing(
    *,
    deterministic_routing: dict[str, Any],
    model: LearnedRouterModel | dict[str, Any] | None = None,
    features: dict[str, Any] | None = None,
    question: str | None = None,
    safe_recall: dict[str, Any] | None = None,
    expanded_recall: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not deterministic_routing:
        raise ValueError("Hybrid routing requires a deterministic decision.")
    route = deterministic_routing["route"]
    if route in {"blocked", "retrieval"}:
        return {
            **deepcopy(deterministic_routing),
            "router": {
                "source": "deterministic",
                "deterministicRoute": route,
                "selectedRoute": route,
                "vetoReason": "hard_policy_route",
            },
        }
    learned = model if isinstance(model, LearnedRouterModel) else LearnedRouterModel(model or {})
    safe = safe_recall or {}
    expanded = expanded_recall or safe
    values = features or extract_router_features(
        question=str(question or ""), safe_recall=safe, expanded_recall=expanded
    )
    prediction = learned.predict(values)
    config = options or {}
    probability = prediction["microSafeProbability"]
    thresholds = prediction["thresholds"]
    veto = None
    if probability >= thresholds["microProbabilityMinimum"]:
        if _eligible(safe, config, "micro"):
            selected = "micro"
        else:
            selected = "meso" if _eligible(expanded, config, "meso") else "full"
            veto = "micro_not_deterministically_eligible"
    elif probability <= thresholds["fullProbabilityMaximum"]:
        selected = "full"
    else:
        selected = "meso" if _eligible(expanded, config, "meso") else "full"
        if selected == "full":
            veto = "meso_not_deterministically_eligible"
    return {
        **deepcopy(deterministic_routing),
        "route": selected,
        "router": {
            "source": "learned",
            "deterministicRoute": route,
            "selectedRoute": selected,
            "modelId": prediction["modelId"],
            "microSafeProbability": round(probability, 6),
            "confidence": round(prediction["confidence"], 6),
            "thresholds": thresholds,
            "vetoReason": veto,
            "featureSchemaVersion": learned.artifact["featureSchemaVersion"],
        },
    }


def _eligible(recall: dict[str, Any], config: dict[str, Any], tier: str) -> bool:
    atoms = recall.get("atoms", [])
    prefix = "micro" if tier == "micro" else "meso"
    max_tokens = (
        config.get("learnedMicroMaxEvidenceTokens", 70)
        if tier == "micro"
        else config.get("mesoMaxEvidenceTokens", 240)
    )
    return (
        len(atoms) >= 2
        and len({atom.get("documentId") for atom in atoms}) >= 2
        and recall.get("structuralChain") is True
        and recall.get("trusted") is True
        and recall.get("queryCoverage", 0)
        >= float(config.get(f"{prefix}MinimumCoverage", 0.45 if tier == "micro" else 0.25))
        and recall.get("intentCoverage", 0)
        >= float(config.get(f"{prefix}MinimumIntentCoverage", 0.15 if tier == "micro" else 0.08))
        and recall.get("maximumSensitivity", 0) <= float(config.get("maxSensitivity", 0.5))
        and recall.get("estimatedEvidenceTokens", 0) <= int(max_tokens)
    )
