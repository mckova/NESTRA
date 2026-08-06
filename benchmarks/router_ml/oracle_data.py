"""Convert historical oracle artifacts into privacy-safe router rows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nestra.ml.features import extract_oracle_router_features


def load_oracle_router_rows(
    file_path: str | Path, *, source: str | None = None, quality_margin: float = 0.05
) -> list[dict[str, Any]]:
    artifact = json.loads(Path(file_path).read_text(encoding="utf-8"))
    output = []
    for example in artifact.get("examples", []):
        entry = next(
            (
                (name, system)
                for name, system in example.get("systems", {}).items()
                if isinstance(system, dict) and system.get("micro")
            ),
            None,
        )
        if entry is None:
            raise ValueError(f"Oracle example {example.get('id')} has no Micro system.")
        system_name, system = entry
        micro = system["micro"]
        lock = micro.get("accuracyLockWouldAccept") or micro.get("accuracyLock") or {}
        lock_accepted = lock.get("accepted") is True
        full = (
            example.get("systems", {}).get("adaptiveMemoryNestra")
            or example.get("systems", {}).get("adaptiveMemoryHive")
            or {}
        )
        raw_quality = (
            bool(
                __import__("re").search(r"micro(?:nestra|hive)100", system_name, __import__("re").I)
            )
            and system.get("quality", {}).get("tokenF1") is not None
        )
        non_inferior = (
            float(system["quality"]["tokenF1"])
            >= float(full["quality"]["tokenF1"]) - quality_margin
            if raw_quality and full.get("quality", {}).get("tokenF1") is not None
            else True
        )
        output.append(
            {
                "id": example.get("id"),
                "features": extract_oracle_router_features(example, system),
                "label": int(lock_accepted and non_inferior),
                "metadata": {
                    "source": source or str(file_path),
                    "systemName": system_name,
                    "lockAccepted": lock_accepted,
                    "nonInferior": non_inferior,
                    "qualityMargin": quality_margin,
                },
            }
        )
    return output
