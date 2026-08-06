"""Versioned numeric feature extraction for the learned router."""

from __future__ import annotations

import math
import re
from typing import Any

from ..project_memory import tokenize_project_text
from ..routing import is_retrieval_intent

ROUTER_FEATURE_SCHEMA_VERSION = 1
ROUTER_FEATURE_NAMES = (
    "question_length",
    "query_term_count",
    "reasoning_cues",
    "binary_question",
    "retrieval_intent",
    "safe_query_coverage",
    "safe_intent_coverage",
    "structural_chain",
    "evidence_tokens",
    "atom_count",
    "document_count",
    "bridge_count",
    "expanded_query_coverage",
    "expanded_intent_coverage",
    "maximum_sensitivity",
)


def extract_router_features(
    *, question: str, safe_recall: dict[str, Any], expanded_recall: dict[str, Any] | None = None
) -> dict[str, float]:
    if not str(question).strip():
        raise ValueError("Router features require a question.")
    expanded = expanded_recall or safe_recall
    atoms = expanded.get("atoms", [])
    return _row(
        {
            "question_length": _scale_log(len(question), 1_000),
            "query_term_count": min(1, len(tokenize_project_text(question)) / 30),
            "reasoning_cues": _reasoning_score(question),
            "binary_question": float(_binary(question)),
            "retrieval_intent": float(is_retrieval_intent(question)),
            "safe_query_coverage": _unit(safe_recall.get("queryCoverage")),
            "safe_intent_coverage": _unit(safe_recall.get("intentCoverage")),
            "structural_chain": float(bool(expanded.get("structuralChain"))),
            "evidence_tokens": min(1, float(expanded.get("estimatedEvidenceTokens", 0)) / 300),
            "atom_count": min(1, len(atoms) / 6),
            "document_count": min(1, len({atom.get("documentId") for atom in atoms}) / 6),
            "bridge_count": min(1, len(expanded.get("bridgeEntityIds", [])) / 4),
            "expanded_query_coverage": _unit(expanded.get("queryCoverage")),
            "expanded_intent_coverage": _unit(expanded.get("intentCoverage")),
            "maximum_sensitivity": _unit(expanded.get("maximumSensitivity")),
        }
    )


def extract_oracle_router_features(
    example: dict[str, Any], system: dict[str, Any]
) -> dict[str, float]:
    micro = system.get("micro", {})
    atoms = (
        micro.get("evidenceAtoms", []) if isinstance(micro.get("evidenceAtoms", []), list) else []
    )
    atom_intent = [
        float(row) for row in micro.get("atomIntentCoverage", []) if isinstance(row, (int, float))
    ]
    question = str(example.get("question", ""))
    query_coverage = _unit(micro.get("queryCoverage"))
    intent_coverage = _unit(micro.get("intentCoverage", min([*atom_intent, query_coverage])))
    structural = micro.get("structuralChain") is True
    return _row(
        {
            "question_length": _scale_log(len(question), 1_000),
            "query_term_count": min(1, len(tokenize_project_text(question)) / 30),
            "reasoning_cues": _reasoning_score(question),
            "binary_question": float(_binary(question)),
            "retrieval_intent": float(is_retrieval_intent(question)),
            "safe_query_coverage": query_coverage,
            "safe_intent_coverage": intent_coverage,
            "structural_chain": float(structural),
            "evidence_tokens": min(
                1,
                float(
                    micro.get("estimatedCompactCallTokens", micro.get("actualCompactCallTokens", 0))
                    or 0
                )
                / 300,
            ),
            "atom_count": min(1, len(atoms) / 6),
            "document_count": min(
                1, len({atom.get("title") for atom in atoms if atom.get("title")}) / 6
            ),
            "bridge_count": 0.25 if structural else 0,
            "expanded_query_coverage": query_coverage,
            "expanded_intent_coverage": intent_coverage,
            "maximum_sensitivity": 0,
        }
    )


def feature_vector(features: dict[str, Any]) -> list[float]:
    return [_finite(features.get(name), 0) for name in ROUTER_FEATURE_NAMES]


def _row(values: dict[str, Any]) -> dict[str, float]:
    return {name: _finite(values.get(name), 0) for name in ROUTER_FEATURE_NAMES}


def _reasoning_score(question: str) -> float:
    matches = re.findall(
        r"\b(?:why|how|compare|contrast|explain|relationship|both|difference|cause|effect|infer|summarize)\b|(?:למה|כיצד|השווה|השווי|הסבר|הסבירי|קשר|הבדל|סיבה|תוצאה|הסק|סכמי)",
        question,
        re.I,
    )
    return min(1, len(matches) / 4)


def _binary(question: str) -> bool:
    return bool(
        re.match(
            r"^(?:are|is|was|were|do|does|did|can|could|will|would|has|have|had)\b|^(?:האם|האם יש|יש)\b",
            question.strip(),
            re.I,
        )
    )


def _scale_log(value: float, maximum: float) -> float:
    return min(1, math.log1p(max(0, value)) / math.log1p(maximum))


def _unit(value: object) -> float:
    return max(0.0, min(1.0, _finite(value, 0)))


def _finite(value: object, fallback: float) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else fallback
    except (TypeError, ValueError):
        return fallback
