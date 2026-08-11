from __future__ import annotations

from nestra import (
    compile_atomic_evidence,
    evaluate_accuracy_lock,
    ground_answer_span,
    micro_prompt,
    route_nestra_query,
)

DOCUMENTS = [
    {"title": "Bobbi Bacha", "text": "Bobbi Bacha was portrayed by actress Sissy Spacek."},
    {
        "title": "Sissy Spacek",
        "text": "Mary Elizabeth Spacek is an American actress known as Sissy Spacek.",
    },
]


def test_atomic_evidence_is_two_document_and_bounded():
    compilation = compile_atomic_evidence(
        "What is Sissy Spacek's middle name?",
        DOCUMENTS,
        target_total_tokens=100,
        max_output_tokens=16,
    )
    assert len(compilation["atoms"]) == 2
    assert len({row["docIndex"] for row in compilation["atoms"]}) == 2
    assert compilation["estimatedTotalTokens"] <= 100
    assert micro_prompt("question", compilation).startswith("Q:question\nE:")


def test_accuracy_lock_accepts_grounded_and_rejects_unsupported():
    compilation = compile_atomic_evidence("What is Sissy Spacek's middle name?", DOCUMENTS)
    assert evaluate_accuracy_lock("What is Sissy Spacek's middle name?", "Elizabeth", compilation)[
        "accepted"
    ]
    assert not evaluate_accuracy_lock(
        "What is Sissy Spacek's middle name?", "Unsupported", compilation
    )["accepted"]
    assert ground_answer_span("Elizabeth, Texas", compilation["evidenceText"]) == "Elizabeth"


def test_deterministic_router_preserves_explicit_retrieval():
    recall = {
        "atoms": [{"documentId": "a", "trust": "trusted", "sensitivity": 0}],
        "queryCoverage": 1,
        "intentCoverage": 1,
        "trusted": True,
        "maximumSensitivity": 0,
        "structuralChain": False,
        "estimatedEvidenceTokens": 10,
    }
    result = route_nestra_query(
        question="Show the evidence sources", safe_recall=recall, mode="retrieval"
    )
    assert result["route"] == "retrieval" and result["authorized"]
