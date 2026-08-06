"""Deterministic route selection before optional learned routing."""

from __future__ import annotations

import re
from typing import Any

from .project_memory import evaluate_pre_call_gate
from .security import detect_prompt_injection

NESTRA_ROUTES = ("blocked", "retrieval", "micro", "meso", "full")


def route_nestra_query(
    *,
    question: str,
    safe_recall: dict[str, Any],
    raw_recall: dict[str, Any] | None = None,
    expanded_recall: dict[str, Any] | None = None,
    mode: str = "auto",
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not str(question).strip():
        raise ValueError("question must be a non-empty string.")
    config = options or {}
    raw = raw_recall or safe_recall
    expanded = expanded_recall or safe_recall
    max_sensitivity = float(config.get("maxSensitivity", 0.5))
    unsafe = [
        atom
        for atom in raw.get("atoms", [])
        if atom.get("trust") != "trusted" or atom.get("sensitivity", 0) > max_sensitivity
    ]
    unsafe_relevant = bool(unsafe) and raw.get("queryCoverage", 0) >= float(
        config.get("unsafeRelevance", 0.2)
    )
    injection_flags = list(
        dict.fromkeys(
            flag
            for atom in raw.get("atoms", [])
            for flag in detect_prompt_injection(atom.get("text", ""))["flags"]
        )
    )
    if injection_flags:
        return _decision(
            "blocked",
            ["prompt_injection_in_evidence", *injection_flags],
            False,
            {"microGate": None},
        )
    if unsafe_relevant and safe_recall.get("queryCoverage", 0) < float(
        config.get("minimumSafeCoverage", 0.2)
    ):
        return _decision(
            "blocked", ["relevant_evidence_not_authorized"], False, {"microGate": None}
        )
    requested = str(mode or "auto").lower()
    if (
        requested == "retrieval" or (requested == "auto" and is_retrieval_intent(question))
    ) and safe_recall.get("atoms"):
        return _decision("retrieval", ["generation_not_required"], True, {"microGate": None})
    micro_gate = evaluate_pre_call_gate(
        question,
        safe_recall,
        requireMultiDocument=config.get("requireMultiDocument", True),
        minimumCoverage=config.get("microMinimumCoverage", 0.45),
        minimumIntentCoverage=config.get("microMinimumIntentCoverage", 0.15),
        maxEvidenceTokens=config.get("microMaxEvidenceTokens", 55),
        maxSensitivity=max_sensitivity,
    )
    if micro_gate["route"] == "micro":
        return _decision("micro", [], True, {"microGate": micro_gate})
    if micro_gate["route"] == "blocked":
        return _decision("blocked", micro_gate["reasons"], False, {"microGate": micro_gate})
    atoms = expanded.get("atoms", [])
    reasons = []
    if len(atoms) < 2:
        reasons.append("insufficient_facts")
    if (
        config.get("requireMultiDocument", True) is not False
        and len({atom.get("documentId") for atom in atoms}) < 2
    ):
        reasons.append("missing_second_document")
    if config.get("requireMultiDocument", True) is not False and not expanded.get(
        "structuralChain"
    ):
        reasons.append("no_structural_chain")
    if expanded.get("queryCoverage", 0) < float(config.get("mesoMinimumCoverage", 0.25)):
        reasons.append("low_query_coverage")
    if expanded.get("intentCoverage", 0) < float(config.get("mesoMinimumIntentCoverage", 0.08)):
        reasons.append("low_intent_coverage")
    if expanded.get("trusted") is not True:
        reasons.append("untrusted_evidence")
    if expanded.get("maximumSensitivity", 0) > max_sensitivity:
        reasons.append("sensitive_evidence")
    if expanded.get("estimatedEvidenceTokens", 0) > int(config.get("mesoMaxEvidenceTokens", 240)):
        reasons.append("evidence_exceeds_meso_budget")
    return _decision(
        "meso" if not reasons else "full",
        list(dict.fromkeys([*micro_gate["reasons"], *reasons])),
        True,
        {"microGate": micro_gate, "mesoReasons": reasons},
    )


def is_retrieval_intent(question: str) -> bool:
    return bool(
        re.search(
            r"\b(?:find|show|list|retrieve|return)\b.{0,30}\b(?:sources?|evidence|passages?|documents?|facts?)\b",
            question,
            re.I | re.S,
        )
        or re.search(
            r"(?:מצא|מצאי|הצג|הציגי|תראה|תראי|רשום|רשמי).{0,30}(?:מקורות|ראיות|קטעים|מסמכים|עובדות)",
            question,
        )
    )


def _decision(
    route: str, reasons: list[str], authorized: bool, checks: dict[str, Any]
) -> dict[str, Any]:
    return {
        "route": route,
        "reasons": list(dict.fromkeys(reasons)),
        "authorized": authorized,
        "checks": checks,
    }
