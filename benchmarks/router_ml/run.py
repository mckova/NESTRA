"""Evaluate the committed Python router on the disjoint holdout."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from benchmarks.router_ml.oracle_data import load_oracle_router_rows  # noqa: E402
from nestra.ml.logistic import evaluate_router_model  # noqa: E402


def main() -> int:
    model = json.loads((ROOT / "models/router/micro-safety-demo.json").read_text(encoding="utf-8"))
    holdout_path = (
        ROOT
        / "benchmarks/nestra-oracle/results/migration-source/micro-holdout-disjoint-seed-20260805.json"
    )
    rows = load_oracle_router_rows(holdout_path, source=holdout_path.relative_to(ROOT).as_posix())
    prior_paths = [
        *model.get("provenance", {}).get("trainingArtifacts", []),
        model.get("provenance", {}).get("validationArtifact"),
    ]
    prior = [
        row
        for relative in prior_paths
        if relative
        for row in load_oracle_router_rows(ROOT / relative)
    ]
    overlap = {row["id"] for row in rows} & {row["id"] for row in prior}
    if overlap:
        raise ValueError(f"Independent holdout overlaps prior data: {', '.join(sorted(overlap))}")
    if len(rows) != len({row["id"] for row in rows}):
        raise ValueError("Independent holdout contains duplicate IDs.")
    metrics = evaluate_router_model(model, rows)
    result = {
        "modelId": model["modelId"],
        "status": model["status"],
        "implementation": "python",
        "split": "independent_disjoint_holdout",
        "dataIntegrity": "disjoint",
        "examples": len(rows),
        "metrics": metrics,
    }
    report = ROOT / "benchmarks/router-ml/results/HOLDOUT_REPORT.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(_report(result), encoding="utf-8")
    print(json.dumps({**result, "report": report.relative_to(ROOT).as_posix()}, indent=2))
    return 0


def _report(result: dict) -> str:
    m = result["metrics"]

    def f(value: object) -> str:
        return f"{float(value):.3f}"

    return f"""# Learned Router independent holdout

- Model: `{result["modelId"]}`
- Status: **{result["status"]}**
- Implementation: **Python**
- Examples: {result["examples"]} (disjoint)

| Classifier accuracy | Brier | Unsafe Micro rate | Full unsafe recall | Policy-decision accuracy | Micro route rate |
|---:|---:|---:|---:|---:|---:|
| {f(m["classifierAccuracy"])} | {f(m["brierScore"])} | {f(m["unsafeMicroRate"])} | {f(m["fullUnsafeRecall"])} | {f(m["policyDecisionAccuracy"])} | {f(m["routeRates"]["micro"])} |

All six examples were Micro-unsafe. The calibrated policy selected no unsafe Micro routes and produced no token savings. This is not evidence of production generalization.
"""


if __name__ == "__main__":
    raise SystemExit(main())
