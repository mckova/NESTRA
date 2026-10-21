"""Offline source retrieval with an explicit, conservative showcase policy.

NESTRA's copied compiler and recall implementation are used without modification.
This wrapper adds a deliberately strict lexical relevance rule and redacts blocked
evidence. It does not perform generation, semantic entailment, or authentication.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from typing import Any

from nestra_core.project_memory import compile_project_memory, tokenize_project_text
from nestra_core.security import detect_prompt_injection, sanitize_user_text

from .fixtures import CASE_IDS, CASES, get_documents

FIXED_TIME = datetime(2026, 10, 21, tzinfo=timezone.utc)
# Function words are excluded only from the showcase's exact lexical coverage.
# Preserve the original Hebrew question words as escapes for existing callers.
_QUESTION_WORDS = frozenset(
    {
        "what",
        "who",
        "when",
        "where",
        "how",
        "why",
        "which",
        "is",
        "are",
        "was",
        "were",
        "the",
        "a",
        "an",
        "for",
        "of",
        "to",
        "in",
        "on",
        "at",
        "by",
        "with",
        "does",
        "do",
        "can",
        "should",
        "\u05de\u05d4",
        "\u05de\u05d9",
        "\u05de\u05ea\u05d9",
        "\u05d0\u05d9\u05e4\u05d4",
        "\u05d4\u05d9\u05db\u05df",
        "\u05d0\u05d9\u05da",
        "\u05db\u05d9\u05e6\u05d3",
        "\u05d4\u05d0\u05dd",
        "\u05e9\u05dc",
        "\u05d0\u05ea",
        "\u05e2\u05dc",
    }
)
_REASON_LABELS = {
    "eligible_source_matches": "An eligible source meets the lexical coverage rule",
    "insufficient_lexical_coverage": "No source excerpt meets the configured lexical coverage rule",
    "no_informative_terms": "The question contains no informative retrieval terms",
    "untrusted_source": "The matching source is not marked trusted",
    "sensitive_source": "The matching source exceeds the showcase sensitivity limit",
    "source_instruction_pattern": "An instruction-like pattern was detected in the source",
    "question_instruction_pattern": "An instruction-like pattern was detected in the question",
}


def _unit_option(value: float, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number.")
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 1 or (positive and number == 0):
        raise ValueError(f"{name} must be {'greater than 0 and ' if positive else ''}at most 1.")
    return number


def evaluate_question(
    question: str,
    documents: list[dict[str, Any]],
    *,
    minimum_coverage: float = 1.0,
    maximum_sensitivity: float = 0.5,
) -> dict[str, Any]:
    """Return source excerpts or abstain; never return a generated answer.

    Trust/sensitivity are supplied fixture metadata, not independently verified
    authorization. Coverage is exact Unicode-normalized token overlap against an
    excerpt, without stemming, semantic inference, or a learned relevance model.
    """
    minimum = _unit_option(minimum_coverage, "minimum_coverage", positive=True)
    maximum = _unit_option(maximum_sensitivity, "maximum_sensitivity")
    query = sanitize_user_text(question, field="question", max_chars=1_000)
    policy = {
        "layer": "showcase_policy",
        "minimum_query_coverage": minimum,
        "maximum_sensitivity": maximum,
        "coverage_rule": "informative_query_tokens_in_excerpt",
        "reason_codes": [],
    }
    result: dict[str, Any] = {
        "case_id": "custom",
        "question": query,
        "status": "no_evidence",
        "policy": policy,
        "retrieval": {
            "engine": "NESTRA lexical project memory",
            "candidates_considered": 0,
        },
        "sources": [],
        "provider": {"configured": False, "calls": 0},
        "generated_answer": None,
    }
    if detect_prompt_injection(query)["detected"]:
        result["status"] = "blocked"
        policy["reason_codes"] = ["question_instruction_pattern"]
        return result

    terms = set(tokenize_project_text(query)) - _QUESTION_WORDS
    if not terms:
        policy["reason_codes"] = ["no_informative_terms"]
        return result

    index = compile_project_memory(
        {"projectId": "fictional-narkis", "documents": documents},
        clock=lambda: FIXED_TIME,
        default_trust="untrusted",
    )
    # Inspect policy metadata in memory, then emit only explicitly eligible text.
    # Original recall adds source-quality score even for zero lexical matches;
    # that base score is never treated as proof that a question is supported.
    recall = index.recall(
        query,
        trusted_only=False,
        max_sensitivity=1.0,
        limit=max(2, len(index.facts)),
        max_atoms=max(1, len(index.facts)),
    )
    result["retrieval"]["candidates_considered"] = recall["candidatesConsidered"]
    relevant = []
    for atom in recall["atoms"]:
        excerpt_terms = set(tokenize_project_text(atom["text"]))
        coverage = len(terms & excerpt_terms) / len(terms)
        if coverage >= minimum:
            relevant.append((atom, coverage))

    reasons: set[str] = set()
    eligible = []
    for atom, coverage in relevant:
        rejected = set()
        if atom["trust"] != "trusted":
            rejected.add("untrusted_source")
        if atom["sensitivity"] > maximum:
            rejected.add("sensitive_source")
        if detect_prompt_injection(atom["text"])["detected"]:
            rejected.add("source_instruction_pattern")
        if rejected:
            reasons.update(rejected)
        else:
            eligible.append((atom, coverage))

    if not eligible:
        if relevant:
            result["status"] = "blocked"
            policy["reason_codes"] = sorted(reasons)
        else:
            policy["reason_codes"] = ["insufficient_lexical_coverage"]
        return result

    eligible.sort(
        key=lambda row: (
            -row[0]["retrievalScore"],
            row[0]["documentId"],
            row[0]["factId"],
        )
    )
    result["status"] = "sources_found"
    policy["reason_codes"] = ["eligible_source_matches"]
    result["sources"] = [
        {
            "id": atom["factId"],
            "document_id": atom["documentId"],
            "title": atom["title"],
            "excerpt": atom["text"],
            "source_uri": atom["provenance"]["sourceUri"],
            "query_coverage": round(coverage, 6),
            "provenance": dict(atom["provenance"]),
        }
        for atom, coverage in eligible
    ]
    return result


def run_case(case_id: str) -> dict[str, Any]:
    """Evaluate one named fixture, independent of prior calls."""
    if case_id not in CASES:
        raise ValueError(f"Unknown case: {case_id}")
    case = CASES[case_id]
    result = evaluate_question(case["question"], get_documents())
    result["case_id"] = case_id
    result["title"] = case["title"]
    return result


def run_demo() -> list[dict[str, Any]]:
    return [run_case(case_id) for case_id in CASE_IDS]


def _render_text(results: list[dict[str, Any]]) -> str:
    lines = [
        "NESTRA - offline source retrieval and policy showcase",
        "All policies and records are fictional. No model provider is configured.",
        "Only source excerpts are returned; lexical coverage does not establish truth or completeness.",
    ]
    status_labels = {
        "sources_found": "Eligible sources found - excerpts, not a generated answer",
        "no_evidence": "Insufficient evidence - no answer is generated",
        "blocked": "Blocked by showcase policy - source content is withheld",
    }
    for result in results:
        lines.extend(
            [
                "",
                f"[{result['case_id']}] {result['title']}",
                f"Question: {result['question']}",
                f"Outcome: {status_labels[result['status']]}",
            ]
        )
        for code in result["policy"]["reason_codes"]:
            lines.append(f"Policy: {_REASON_LABELS[code]} ({code})")
        for source in result["sources"]:
            lines.extend(
                [
                    f"Source: {source['title']} | {source['source_uri']}",
                    f"Excerpt: {source['excerpt']}",
                    f"Source identifier: {source['id']}",
                ]
            )
        lines.append("Provider: not configured | calls: 0")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline NESTRA showcase using fictional team policies only"
    )
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON")
    parser.add_argument("--case", choices=CASE_IDS, help="Run one named case instead of all four")
    args = parser.parse_args(argv)
    results = [run_case(args.case)] if args.case else run_demo()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(_render_text(results))
    return 0
