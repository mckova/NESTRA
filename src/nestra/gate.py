"""Deterministic local policy for tool and path requests."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def evaluate_gate(plan: dict[str, Any], request: dict[str, Any] | None = None) -> dict[str, Any]:
    request = request or {}
    action = str(request.get("action", "read"))
    if action in {"network", "shell", "delete"} and action not in set(
        plan.get("allowedActions", [])
    ):
        return {"allowed": False, "reason": f"{action}_not_allowed"}
    candidate = request.get("path")
    if candidate:
        resolved = Path(candidate).resolve()
        prefixes = [Path(row).resolve() for row in plan.get("allowedPaths", [])]
        if not any(resolved == prefix or prefix in resolved.parents for prefix in prefixes):
            return {"allowed": False, "reason": "path_not_allowed"}
    if request.get("containsSecrets"):
        return {"allowed": False, "reason": "secret_material_rejected"}
    return {"allowed": True, "reason": "allowed"}
