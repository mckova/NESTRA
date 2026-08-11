from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from nestra import (
    ScopedMemory,
    compile_project_memory,
    evaluate_pre_call_gate,
    restore_project_memory,
)

DOCUMENTS = [
    {
        "title": "Bobbi Bacha",
        "text": "Bobbi Bacha was portrayed by actress Sissy Spacek.",
        "trust": "trusted",
    },
    {
        "title": "Sissy Spacek",
        "text": "Mary Elizabeth Spacek is an American actress known as Sissy Spacek.",
        "trust": "trusted",
    },
    {"title": "Noise", "text": "Gardens contain trees and flowers.", "trust": "trusted"},
]


def test_compilation_is_deterministic_and_has_provenance():
    def clock():
        return datetime(2026, 1, 1, tzinfo=timezone.utc)

    left = compile_project_memory(
        {"projectId": "casting", "documents": DOCUMENTS}, clock=clock
    ).export()
    right = compile_project_memory(
        {"projectId": "casting", "documents": DOCUMENTS}, clock=clock
    ).export()
    assert left == right
    assert left["stats"]["documents"] == 3
    assert any(row["normalized"] == "sissy spacek" for row in left["entities"])
    assert len(left["facts"][0]["provenance"]["contentHash"]) == 24


def test_recall_finds_trusted_two_document_bridge_and_micro_gate():
    recall = compile_project_memory({"projectId": "casting", "documents": DOCUMENTS}).recall(
        "What is Sissy Spacek's middle name?"
    )
    gate = evaluate_pre_call_gate(
        "What is Sissy Spacek's middle name?", recall, maxEvidenceTokens=80
    )
    assert len(recall["atoms"]) == 2
    assert len(set(recall["documentIds"])) == 2
    assert "Sissy Spacek" in recall["bridgeEntities"]
    assert gate["route"] == "micro"


def test_incomplete_and_untrusted_evidence_fail_closed():
    one = compile_project_memory({"projectId": "one", "documents": DOCUMENTS[:1]}).recall(
        "What is Sissy Spacek's middle name?"
    )
    assert evaluate_pre_call_gate("What is Sissy Spacek's middle name?", one)["route"] == "fallback"
    unsafe_docs = [{**row, "trust": "untrusted"} for row in DOCUMENTS[:2]]
    unsafe = compile_project_memory({"projectId": "unsafe", "documents": unsafe_docs}).recall(
        "What is Sissy Spacek's middle name?", trusted_only=False
    )
    gate = evaluate_pre_call_gate("What is Sissy Spacek's middle name?", unsafe)
    assert gate["route"] == "blocked"
    assert "untrusted_evidence" in gate["reasons"]


def test_snapshot_restores_and_hydrates_scoped_memory():
    index = compile_project_memory({"projectId": "casting", "documents": DOCUMENTS})
    restored = restore_project_memory(index.export())
    assert (
        restored.recall("What is Sissy Spacek's middle name?")["factIds"]
        == index.recall("What is Sissy Spacek's middle name?")["factIds"]
    )
    memory = ScopedMemory()
    assert len(restored.to_scoped_memory(memory, namespace="project:casting")) == 3
    assert (
        len(
            memory.query(
                scope="project", namespace="project:casting", role="builder", trusted_only=True
            )
        )
        == 3
    )
    assert memory.query(scope="project", namespace="project:other", role="builder") == []


def test_duplicate_document_ids_and_malformed_snapshots_are_rejected():
    with pytest.raises(ValueError, match="unique ids"):
        compile_project_memory(
            {
                "projectId": "duplicate",
                "documents": [
                    {"id": "same", "title": "A", "text": "Alpha.", "trust": "trusted"},
                    {"id": "same", "title": "B", "text": "Beta.", "trust": "trusted"},
                ],
            }
        )
    snapshot = compile_project_memory({"projectId": "valid", "documents": DOCUMENTS[:1]}).export()
    del snapshot["facts"][0]["trust"]
    with pytest.raises(ValueError, match="missing required fields"):
        restore_project_memory(snapshot)


def test_snapshot_integrity_rejects_tampered_graph_and_hidden_fields():
    original = compile_project_memory({"projectId": "valid", "documents": DOCUMENTS[:2]}).export()

    snapshot = deepcopy(original)
    snapshot["unexpected"] = "hidden"
    with pytest.raises(ValueError, match="unsupported fields"):
        restore_project_memory(snapshot)

    snapshot = deepcopy(original)
    snapshot["facts"][0]["entityIds"] = []
    with pytest.raises(ValueError, match="entityIds are inconsistent"):
        restore_project_memory(snapshot)

    snapshot = deepcopy(original)
    snapshot["relations"] = []
    snapshot["stats"]["relations"] = 0
    with pytest.raises(ValueError, match="relation set"):
        restore_project_memory(snapshot)


@pytest.mark.parametrize(
    "document",
    [
        {"title": 123, "text": "Alpha."},
        {"title": "A", "text": 123},
        {"title": "A", "text": "", "sentences": ["Alpha."]},
        {"title": "A", "text": "Alpha.", "trust": "maybe"},
        {"title": "A", "text": "Alpha.", "sensitivity": "private"},
        {"title": "A", "text": "Alpha.", "sourceQuality": 2},
        {"id": "", "title": "A", "text": "Alpha."},
    ],
)
def test_document_contract_rejects_invalid_explicit_values(document):
    with pytest.raises(ValueError):
        compile_project_memory({"projectId": "invalid", "documents": [document]})


def test_project_id_and_default_trust_are_strict():
    with pytest.raises(ValueError, match="projectId"):
        compile_project_memory({"projectId": 123, "documents": DOCUMENTS[:1]})
    with pytest.raises(ValueError, match="default_trust"):
        compile_project_memory(
            {"projectId": "valid", "documents": DOCUMENTS[:1]}, default_trust="maybe"
        )
