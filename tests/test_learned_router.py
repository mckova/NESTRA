from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from benchmarks.router_ml.oracle_data import load_oracle_router_rows
from nestra import FileProjectStore, NestraRuntime, load_bundled_router_model
from nestra.ml import (
    ROUTER_FEATURE_NAMES,
    LearnedRouterModel,
    apply_learned_routing,
    evaluate_router_model,
    train_micro_safety_router,
)

ROOT = Path(__file__).resolve().parents[1]


def test_training_is_deterministic_and_artifact_contains_no_raw_text():
    rows = [
        {"label": int(index >= 5), "features": _features(index / 9, 0.9 if index >= 5 else 0.1)}
        for index in range(10)
    ]
    options = {
        "validation_rows": list(reversed(rows)),
        "clock": lambda: datetime(2026, 8, 6, tzinfo=timezone.utc),
        "provenance": {"containsRawText": False},
    }
    left = train_micro_safety_router(rows, **options)
    right = train_micro_safety_router(rows, **options)
    assert left == right
    assert LearnedRouterModel(left).predict(rows[0]["features"])["modelId"] == left["modelId"]
    serialized = json.dumps(left)
    assert (
        '"question":' not in serialized
        and '"answer":' not in serialized
        and '"text":' not in serialized
    )


def test_hard_policy_routes_bypass_model():
    for route in ("blocked", "retrieval"):
        result = apply_learned_routing(
            deterministic_routing={"route": route, "authorized": route != "blocked", "reasons": []}
        )
        assert result["route"] == route
        assert result["router"]["source"] == "deterministic"
        assert result["router"]["vetoReason"] == "hard_policy_route"


def test_micro_proposal_is_vetoed_without_evidence_eligibility():
    result = apply_learned_routing(
        deterministic_routing={
            "route": "full",
            "authorized": True,
            "reasons": ["low_query_coverage"],
        },
        model=_constant_model(0.99),
        features=_features(0.5, 0.5),
        safe_recall=_eligible_recall(queryCoverage=0.1),
        expanded_recall=_eligible_recall(queryCoverage=0.1),
    )
    assert result["route"] == "full"
    assert result["router"]["vetoReason"] == "micro_not_deterministically_eligible"


def test_learned_policy_can_promote_compact_or_choose_full():
    compact = apply_learned_routing(
        deterministic_routing={"route": "meso", "authorized": True, "reasons": []},
        model=_constant_model(0.99),
        features=_features(0.5, 0.5),
        safe_recall=_eligible_recall(estimatedEvidenceTokens=65),
        expanded_recall=_eligible_recall(estimatedEvidenceTokens=65),
    )
    assert compact["route"] == "micro"
    conservative = apply_learned_routing(
        deterministic_routing={"route": "micro", "authorized": True, "reasons": []},
        model=_constant_model(0.01),
        features=_features(0.5, 0.5),
        safe_recall=_eligible_recall(),
        expanded_recall=_eligible_recall(),
    )
    assert conservative["route"] == "full"


def test_committed_python_model_selects_zero_unsafe_micro_on_disjoint_holdout():
    model = load_bundled_router_model()
    rows = load_oracle_router_rows(
        ROOT
        / "benchmarks/nestra-oracle/results/migration-source/micro-holdout-disjoint-seed-20260805.json"
    )
    metrics = evaluate_router_model(model, rows)
    assert all(row["label"] == 0 for row in rows)
    assert metrics["unsafeMicroRate"] == 0
    assert metrics["routeRates"]["micro"] == 0
    assert metrics["fullUnsafeRecall"] == 1
    assert model["provenance"]["implementation"] == "python"


def test_runtime_plan_exposes_learned_provenance(tmp_path: Path):
    runtime = NestraRuntime(
        store=FileProjectStore(tmp_path), router_model=load_bundled_router_model()
    )
    runtime.ingest(
        project_id="casting",
        documents=[
            {
                "title": "Bobbi Bacha",
                "text": "Bobbi Bacha was portrayed by actress Sissy Spacek.",
                "trust": "trusted",
            },
            {
                "title": "Sissy Spacek",
                "text": "Mary Elizabeth Spacek is known as Sissy Spacek.",
                "trust": "trusted",
            },
        ],
    )
    plan = runtime.plan(project_id="casting", question="What is Sissy Spacek's middle name?")
    assert plan["router"]["source"] == "learned"
    assert plan["router"]["modelId"] == load_bundled_router_model()["modelId"]
    assert plan["router"]["thresholds"]["microEnabled"] is False


def _features(primary: float, coverage: float) -> dict[str, float]:
    return {
        name: coverage if index % 2 else primary for index, name in enumerate(ROUTER_FEATURE_NAMES)
    }


def _eligible_recall(**overrides):
    return {
        "atoms": [{"documentId": "a"}, {"documentId": "b"}],
        "structuralChain": True,
        "trusted": True,
        "queryCoverage": 0.8,
        "intentCoverage": 0.4,
        "maximumSensitivity": 0,
        "estimatedEvidenceTokens": 40,
        **overrides,
    }


def _constant_model(probability: float) -> dict:
    artifact = deepcopy(load_bundled_router_model())
    import math

    artifact["coefficients"] = [0.0] * len(ROUTER_FEATURE_NAMES)
    artifact["normalization"] = {
        "means": [0.0] * len(ROUTER_FEATURE_NAMES),
        "standardDeviations": [1.0] * len(ROUTER_FEATURE_NAMES),
    }
    artifact["intercept"] = math.log(probability / (1 - probability))
    artifact["thresholds"] = {
        "fullProbabilityMaximum": 0.2,
        "microProbabilityMinimum": 0.8,
        "microEnabled": True,
        "minimumMicroPrecision": 0.9,
        "minimumFullPrecision": 0.8,
        "minimumMicroSelections": 3,
        "minimumFullSelections": 3,
    }
    return artifact
