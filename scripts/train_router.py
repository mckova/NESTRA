"""Train and calibrate the bundled local Micro-safety router."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from benchmarks.router_ml.oracle_data import load_oracle_router_rows  # noqa: E402
from nestra.ml.logistic import train_micro_safety_router  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--train",
        default="benchmarks/nestra-oracle/results/migration-source/micro-dev-v3.json,benchmarks/nestra-oracle/results/migration-source/micro-100-validation-12-seed-1618033.json",
    )
    parser.add_argument(
        "--validation",
        default="benchmarks/nestra-oracle/results/migration-source/micro-final-holdout-seed-314159.json",
    )
    parser.add_argument("--output", default="models/router/micro-safety-demo.json")
    parser.add_argument("--report", default="benchmarks/router-ml/results/REPORT.md")
    parser.add_argument("--trained-at", default="2026-08-06T00:00:00Z")
    args = parser.parse_args(argv)
    train_paths = [(ROOT / value.strip()).resolve() for value in args.train.split(",")]
    validation_path = (ROOT / args.validation).resolve()
    training = [
        row
        for path in train_paths
        for row in load_oracle_router_rows(path, source=path.relative_to(ROOT).as_posix())
    ]
    validation = load_oracle_router_rows(
        validation_path, source=validation_path.relative_to(ROOT).as_posix()
    )
    _unique(training, "training")
    _unique(validation, "calibration")
    _disjoint(training, validation, "training", "calibration")
    trained_at = datetime.fromisoformat(args.trained_at.replace("Z", "+00:00"))
    artifact = train_micro_safety_router(
        training,
        validation_rows=validation,
        clock=lambda: trained_at,
        provenance={
            "trainingArtifacts": [path.relative_to(ROOT).as_posix() for path in train_paths],
            "validationArtifact": validation_path.relative_to(ROOT).as_posix(),
            "label": "Micro accuracy lock accepted and, when raw Micro quality is available, token F1 is within 0.05 of Adaptive Full",
            "containsRawText": False,
            "implementation": "python",
        },
    )
    output = (ROOT / args.output).resolve()
    report = (ROOT / args.report).resolve()
    packaged = ROOT / "src/nestra/models/micro-safety-demo.json"
    for target in (output, packaged, report):
        target.parent.mkdir(parents=True, exist_ok=True)
    model_text = json.dumps(artifact, ensure_ascii=False, indent=2) + "\n"
    output.write_text(model_text, encoding="utf-8")
    packaged.write_text(model_text, encoding="utf-8")
    report.write_text(_report(artifact), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "packagedOutput": str(packaged),
                "report": str(report),
                "modelId": artifact["modelId"],
                "training": artifact["training"],
                "validation": artifact["validation"],
            },
            indent=2,
        )
    )
    return 0


def _report(model: dict) -> str:
    def metric(value: object) -> str:
        return f"{float(value):.3f}"

    threshold = model["thresholds"]
    train = model["training"]
    validation = model["validation"]
    return f"""# Learned Router report

- Model: `{model["modelId"]}`
- Status: **{model["status"]}**
- Implementation: **Python**
- Feature schema: {model["featureSchemaVersion"]}

## Data

- Training: {train["examples"]} examples ({train["positives"]} Micro-safe, {train["negatives"]} unsafe).
- Calibration: {validation["examples"]} examples ({validation["positives"]} Micro-safe, {validation["negatives"]} unsafe).
- Raw questions, answers, and evidence are not stored in the model artifact.

## Calibrated routing

- Full when `p(Micro-safe) <= {threshold["fullProbabilityMaximum"]}`.
- Micro when `p(Micro-safe) >= {threshold["microProbabilityMinimum"]}`; {"enabled" if threshold["microEnabled"] else "disabled because calibration did not meet precision/support constraints"}.
- Meso between the thresholds. Blocked and Retrieval-only remain deterministic.

## Metrics

| Split | Classifier accuracy | Brier | Micro precision | Unsafe Micro rate | Full unsafe recall | Policy-decision accuracy |
|---|---:|---:|---:|---:|---:|---:|
| Train | {metric(train["metrics"]["classifierAccuracy"])} | {metric(train["metrics"]["brierScore"])} | {metric(train["metrics"]["microPrecision"])} | {metric(train["metrics"]["unsafeMicroRate"])} | {metric(train["metrics"]["fullUnsafeRecall"])} | {metric(train["metrics"]["policyDecisionAccuracy"])} |
| Calibration | {metric(validation["metrics"]["classifierAccuracy"])} | {metric(validation["metrics"]["brierScore"])} | {metric(validation["metrics"]["microPrecision"])} | {metric(validation["metrics"]["unsafeMicroRate"])} | {metric(validation["metrics"]["fullUnsafeRecall"])} | {metric(validation["metrics"]["policyDecisionAccuracy"])} |

This real, reproducible Python training pipeline remains experimental. The sample is too small for a savings or non-inferiority claim.
"""


def _unique(rows: list[dict], name: str) -> None:
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{name} contains duplicate oracle IDs.")


def _disjoint(left: list[dict], right: list[dict], left_name: str, right_name: str) -> None:
    overlap = sorted({row["id"] for row in left} & {row["id"] for row in right})
    if overlap:
        raise ValueError(f"{left_name} and {right_name} overlap: {', '.join(overlap)}")


if __name__ == "__main__":
    raise SystemExit(main())
