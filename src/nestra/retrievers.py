"""External retriever normalization with fail-closed trust defaults."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def assert_retriever(retriever: object) -> None:
    if retriever is None or not callable(getattr(retriever, "retrieve", None)):
        raise ValueError("retriever must implement retrieve().")


def normalize_retrieved_documents(
    value: object, *, default_trust: str = "untrusted"
) -> list[dict[str, Any]]:
    rows = value.get("documents", []) if isinstance(value, dict) else value
    if not isinstance(rows, list):
        raise ValueError("Retriever output must be a list or {'documents': [...]}.")
    output = []
    for index, row in enumerate(rows):
        if (
            not isinstance(row, dict)
            or not str(row.get("title", "")).strip()
            or not str(row.get("text", "")).strip()
        ):
            raise ValueError(f"Retriever document {index} requires title and text.")
        trust = (
            row.get("trust")
            if row.get("trust") in {"trusted", "untrusted"}
            else ("trusted" if default_trust == "trusted" else "untrusted")
        )
        output.append(
            {
                **deepcopy(row),
                "trust": trust,
                "sensitivity": _unit(row.get("sensitivity"), 0),
                "sourceQuality": _unit(
                    row.get("sourceQuality", row.get("score")), 1 if trust == "trusted" else 0.5
                ),
            }
        )
    return output


def _unit(value: object, fallback: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return fallback
