"""Dependency-free weighted Logistic Regression with conservative calibration."""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from .features import ROUTER_FEATURE_NAMES, ROUTER_FEATURE_SCHEMA_VERSION, feature_vector

MODEL_KIND = "nestra-micro-safety-logistic"


class LearnedRouterModel:
    def __init__(self, artifact: dict[str, Any]) -> None:
        validate_artifact(artifact)
        self.artifact = deepcopy(artifact)

    def predict(self, features: dict[str, Any]) -> dict[str, Any]:
        raw = feature_vector(features)
        means = self.artifact["normalization"]["means"]
        deviations = self.artifact["normalization"]["standardDeviations"]
        normalized = [(value - means[index]) / deviations[index] for index, value in enumerate(raw)]
        logit = self.artifact["intercept"] + sum(
            value * self.artifact["coefficients"][index] for index, value in enumerate(normalized)
        )
        probability = _sigmoid(logit)
        return {
            "microSafeProbability": probability,
            "confidence": max(probability, 1 - probability),
            "modelId": self.artifact["modelId"],
            "thresholds": deepcopy(self.artifact["thresholds"]),
        }

    def export(self) -> dict[str, Any]:
        return deepcopy(self.artifact)


def train_micro_safety_router(
    rows: Iterable[dict[str, Any]],
    *,
    validation_rows: Iterable[dict[str, Any]] | None = None,
    clock: Callable[[], datetime] | None = None,
    status: str = "experimental",
    epochs: int = 1_200,
    learning_rate: float = 0.08,
    l2: float = 0.02,
    minimum_micro_precision: float = 0.9,
    minimum_full_precision: float = 0.8,
    minimum_micro_selections: int = 3,
    minimum_full_selections: int = 3,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    training = _normalize_rows(list(rows), "training")
    validation = _normalize_rows(
        list(validation_rows) if validation_rows is not None else list(rows), "validation"
    )
    positives = sum(row["label"] for row in training)
    negatives = len(training) - positives
    if not positives or not negatives:
        raise ValueError("Router training requires both safe and unsafe Micro examples.")
    columns = [[row["features"][name] for row in training] for name in ROUTER_FEATURE_NAMES]
    means = [_mean(column) for column in columns]
    deviations = [_deviation(column, means[index]) for index, column in enumerate(columns)]
    vectors = [_standardize(feature_vector(row["features"]), means, deviations) for row in training]
    positive_weight = len(training) / (2 * positives)
    negative_weight = len(training) / (2 * negatives)
    coefficients = [0.0] * len(ROUTER_FEATURE_NAMES)
    intercept = math.log((positives + 0.5) / (negatives + 0.5))
    for epoch in range(max(1, int(epochs))):
        gradient = [0.0] * len(coefficients)
        intercept_gradient = 0.0
        for row, vector in zip(training, vectors, strict=True):
            probability = _sigmoid(intercept + _dot(coefficients, vector))
            weight = positive_weight if row["label"] == 1 else negative_weight
            error = (probability - row["label"]) * weight
            intercept_gradient += error
            for index, value in enumerate(vector):
                gradient[index] += error * value
        step = float(learning_rate) / math.sqrt(1 + epoch / 100)
        intercept -= step * intercept_gradient / len(training)
        coefficients = [
            value - step * (gradient[index] / len(training) + float(l2) * value)
            for index, value in enumerate(coefficients)
        ]

    def predict(features: dict[str, Any]) -> float:
        return _sigmoid(
            intercept
            + _dot(coefficients, _standardize(feature_vector(features), means, deviations))
        )

    validation_predictions = [
        {"label": row["label"], "probability": predict(row["features"])} for row in validation
    ]
    thresholds = _calibrate(
        validation_predictions,
        minimum_micro_precision,
        minimum_full_precision,
        minimum_micro_selections,
        minimum_full_selections,
    )
    trained_at = (
        (clock or (lambda: datetime.now(timezone.utc)))()
        .astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
    artifact = {
        "schemaVersion": 1,
        "kind": MODEL_KIND,
        "status": status,
        "featureSchemaVersion": ROUTER_FEATURE_SCHEMA_VERSION,
        "featureNames": list(ROUTER_FEATURE_NAMES),
        "trainedAt": trained_at,
        "normalization": {
            "means": [_round(value) for value in means],
            "standardDeviations": [_round(value) for value in deviations],
        },
        "coefficients": [_round(value) for value in coefficients],
        "intercept": _round(intercept),
        "thresholds": thresholds,
        "training": {
            "examples": len(training),
            "positives": positives,
            "negatives": negatives,
            "epochs": int(epochs),
            "learningRate": learning_rate,
            "l2": l2,
            "metrics": _evaluate_predictions(
                [
                    {"label": row["label"], "probability": predict(row["features"])}
                    for row in training
                ],
                thresholds,
            ),
        },
        "validation": {
            "examples": len(validation),
            "positives": sum(row["label"] for row in validation),
            "negatives": len(validation) - sum(row["label"] for row in validation),
            "metrics": _evaluate_predictions(validation_predictions, thresholds),
        },
        "provenance": deepcopy(provenance or {}),
    }
    artifact["modelId"] = f"router-{hashlib.sha256(_canonical(artifact).encode()).hexdigest()[:16]}"
    return artifact


def evaluate_router_model(
    artifact: dict[str, Any], rows: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    model = LearnedRouterModel(artifact)
    normalized = _normalize_rows(list(rows), "evaluation")
    predictions = [
        {
            "label": row["label"],
            "probability": model.predict(row["features"])["microSafeProbability"],
        }
        for row in normalized
    ]
    return _evaluate_predictions(predictions, artifact["thresholds"])


def validate_artifact(artifact: dict[str, Any]) -> None:
    if (
        not isinstance(artifact, dict)
        or artifact.get("schemaVersion") != 1
        or artifact.get("kind") != MODEL_KIND
    ):
        raise ValueError("Unsupported learned router artifact.")
    if artifact.get("featureSchemaVersion") != ROUTER_FEATURE_SCHEMA_VERSION or artifact.get(
        "featureNames"
    ) != list(ROUTER_FEATURE_NAMES):
        raise ValueError("Learned router feature schema mismatch.")
    length = len(ROUTER_FEATURE_NAMES)
    for key, value in (
        ("coefficients", artifact.get("coefficients")),
        ("normalization.means", artifact.get("normalization", {}).get("means")),
        (
            "normalization.standardDeviations",
            artifact.get("normalization", {}).get("standardDeviations"),
        ),
    ):
        if (
            not isinstance(value, list)
            or len(value) != length
            or not all(_finite(item) for item in value)
        ):
            raise ValueError(f"Invalid learned router field: {key}.")
    if not all(value > 0 for value in artifact["normalization"]["standardDeviations"]):
        raise ValueError("Learned router deviations must be positive.")
    if not _finite(artifact.get("intercept")):
        raise ValueError("Invalid learned router intercept.")
    thresholds = artifact.get("thresholds", {})
    full, micro = (
        thresholds.get("fullProbabilityMaximum"),
        thresholds.get("microProbabilityMinimum"),
    )
    if (
        not _finite(full)
        or not _finite(micro)
        or not 0 <= full <= 1
        or not 0 <= micro <= 1.000001
        or full >= micro
        or thresholds.get("microEnabled") is not (micro <= 1)
    ):
        raise ValueError("Learned router thresholds are inconsistent.")
    if not all(
        isinstance(thresholds.get(key), int) and thresholds[key] >= 1
        for key in ("minimumMicroSelections", "minimumFullSelections")
    ):
        raise ValueError("Learned router calibration support is invalid.")
    if not isinstance(artifact.get("modelId"), str) or not __import__("re").fullmatch(
        r"router-[a-f0-9]{16}", artifact["modelId"]
    ):
        raise ValueError("Invalid learned router model ID.")


def _calibrate(
    predictions: list[dict[str, Any]],
    min_micro_precision: float,
    min_full_precision: float,
    min_micro: int,
    min_full: int,
) -> dict[str, Any]:
    values = sorted({_round(row["probability"]) for row in predictions})
    micro = 1.000001
    for threshold in values:
        selected = [row for row in predictions if row["probability"] >= threshold]
        if len(selected) >= min_micro and _precision(selected, 1) >= min_micro_precision:
            micro = threshold
            break
    full = 0.0
    for threshold in (value for value in values if value < micro):
        selected = [row for row in predictions if row["probability"] <= threshold]
        if len(selected) >= min_full and _precision(selected, 0) >= min_full_precision:
            full = threshold
    return {
        "fullProbabilityMaximum": _round(full),
        "microProbabilityMinimum": _round(micro),
        "microEnabled": micro <= 1,
        "minimumMicroPrecision": min_micro_precision,
        "minimumFullPrecision": min_full_precision,
        "minimumMicroSelections": min_micro,
        "minimumFullSelections": min_full,
    }


def _evaluate_predictions(
    predictions: list[dict[str, Any]], thresholds: dict[str, Any]
) -> dict[str, Any]:
    routes = [{**row, "route": _route(row["probability"], thresholds)} for row in predictions]
    micro = [row for row in routes if row["route"] == "micro"]
    full = [row for row in routes if row["route"] == "full"]
    positives = sum(row["label"] for row in predictions)
    negatives = len(predictions) - positives
    decisions = [row for row in routes if row["route"] != "meso"]
    correct = [
        row
        for row in decisions
        if (row["route"] == "micro" and row["label"] == 1)
        or (row["route"] == "full" and row["label"] == 0)
    ]
    epsilon = 1e-9
    return {
        "classifierAccuracy": _round(
            sum((row["probability"] >= 0.5) == bool(row["label"]) for row in predictions)
            / len(predictions)
        ),
        "brierScore": _round(
            _mean([(row["probability"] - row["label"]) ** 2 for row in predictions])
        ),
        "logLoss": _round(
            -_mean(
                [
                    row["label"] * math.log(max(epsilon, row["probability"]))
                    + (1 - row["label"]) * math.log(max(epsilon, 1 - row["probability"]))
                    for row in predictions
                ]
            )
        ),
        "microPrecision": _round(_precision(micro, 1)),
        "microRecall": _round(
            sum(row["label"] == 1 for row in micro) / positives if positives else 0
        ),
        "unsafeMicroRate": _round(
            sum(row["label"] == 0 for row in micro) / negatives if negatives else 0
        ),
        "fullUnsafePrecision": _round(_precision(full, 0)),
        "fullUnsafeRecall": _round(
            sum(row["label"] == 0 for row in full) / negatives if negatives else 0
        ),
        "fullOverRoutingRate": _round(
            sum(row["label"] == 1 for row in full) / positives if positives else 0
        ),
        "policyDecisionAccuracy": _round(len(correct) / len(decisions) if decisions else 0),
        "policyDecisionCoverage": _round(len(decisions) / len(predictions)),
        "routeRates": {
            name: _round(sum(row["route"] == name for row in routes) / len(routes))
            for name in ("micro", "meso", "full")
        },
    }


def _normalize_rows(rows: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    if not rows:
        raise ValueError(f"{name} rows must be non-empty.")
    output = []
    for index, row in enumerate(rows):
        if row.get("label") not in (0, 1, False, True):
            raise ValueError(f"{name} row {index} has an invalid label.")
        output.append(
            {
                "features": {
                    feature: float(row.get("features", {}).get(feature, 0) or 0)
                    for feature in ROUTER_FEATURE_NAMES
                },
                "label": int(row["label"]),
            }
        )
    return output


def _route(probability: float, thresholds: dict[str, Any]) -> str:
    if probability >= thresholds["microProbabilityMinimum"]:
        return "micro"
    if probability <= thresholds["fullProbabilityMaximum"]:
        return "full"
    return "meso"


def _standardize(values: list[float], means: list[float], deviations: list[float]) -> list[float]:
    return [(value - means[index]) / deviations[index] for index, value in enumerate(values)]


def _dot(left: list[float], right: list[float]) -> float:
    return sum(value * right[index] for index, value in enumerate(left))


def _mean(values: list[float]) -> float:
    return sum(values) / max(1, len(values))


def _deviation(values: list[float], average: float) -> float:
    return math.sqrt(_mean([(value - average) ** 2 for value in values])) or 1


def _precision(rows: list[dict[str, Any]], label: int) -> float:
    return sum(row["label"] == label for row in rows) / len(rows) if rows else 0


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1 / (1 + math.exp(-min(60, value)))
    exp = math.exp(max(-60, value))
    return exp / (1 + exp)


def _round(value: float) -> float:
    return round(float(value), 6)


def _finite(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
