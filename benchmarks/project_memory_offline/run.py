"""Network-free routing and safety benchmark."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from nestra import compile_project_memory, evaluate_pre_call_gate  # noqa: E402


def main() -> int:
    directory = ROOT / "benchmarks/project-memory-offline"
    cases = json.loads((directory / "cases.json").read_text(encoding="utf-8"))
    rows = []
    for fixture in cases:
        started = time.perf_counter()
        memory = compile_project_memory(
            {"projectId": f"offline-{fixture['id']}", "documents": fixture["documents"]}
        )
        ingestion = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        recall_options = fixture.get("recall", {})
        recall = memory.recall(
            fixture["question"],
            trusted_only=recall_options.get("trustedOnly", True),
            max_sensitivity=recall_options.get("maxSensitivity", 0.5),
            limit=8,
        )
        latency = (time.perf_counter() - started) * 1000
        gate = evaluate_pre_call_gate(fixture["question"], recall, **fixture.get("gate", {}))
        missing = [
            reason for reason in fixture.get("expectedReasons", []) if reason not in gate["reasons"]
        ]
        rows.append(
            {
                "id": fixture["id"],
                "expectedRoute": fixture["expectedRoute"],
                "actualRoute": gate["route"],
                "passed": gate["route"] == fixture["expectedRoute"] and not missing,
                "expectedReasons": fixture.get("expectedReasons", []),
                "actualReasons": gate["reasons"],
                "missingReasons": missing,
                "ingestionLatencyMs": ingestion,
                "recallLatencyMs": latency,
                "providerTokens": 0,
                "stats": memory.export()["stats"],
            }
        )
    result = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "purpose": "Deterministic routing and safety evaluation only; this does not measure model answer accuracy.",
        "implementation": "python",
        "cases": len(rows),
        "passed": sum(row["passed"] for row in rows),
        "providerTokens": 0,
        "rows": rows,
    }
    output = directory / "results/latest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "cases": result["cases"],
                "passed": result["passed"],
                "providerTokens": 0,
            },
            indent=2,
        )
    )
    return 0 if result["passed"] == result["cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
