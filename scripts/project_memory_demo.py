from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nestra import compile_project_memory, evaluate_pre_call_gate  # noqa: E402

path = (
    ROOT / (sys.argv[1] if len(sys.argv) > 1 else "examples/project-memory/casting.json")
).resolve()
if ROOT not in path.parents:
    raise ValueError("Demo input must stay inside the NESTRA project.")
input_ = json.loads(path.read_text(encoding="utf-8"))
started = time.perf_counter()
memory = compile_project_memory(input_)
ingestion = (time.perf_counter() - started) * 1000
started = time.perf_counter()
recall = memory.recall(input_["question"], trusted_only=True, limit=8)
latency = (time.perf_counter() - started) * 1000
print(
    json.dumps(
        {
            "projectId": input_["projectId"],
            "question": input_["question"],
            "ingestion": {**memory.export()["stats"], "latencyMs": ingestion, "providerTokens": 0},
            "recall": {
                "factIds": recall["factIds"],
                "documentIds": recall["documentIds"],
                "bridgeEntities": recall["bridgeEntities"],
                "queryCoverage": recall["queryCoverage"],
                "intentCoverage": recall["intentCoverage"],
                "estimatedEvidenceTokens": recall["estimatedEvidenceTokens"],
                "latencyMs": latency,
            },
            "preCallGate": evaluate_pre_call_gate(input_["question"], recall, maxEvidenceTokens=80),
        },
        ensure_ascii=False,
        indent=2,
    )
)
