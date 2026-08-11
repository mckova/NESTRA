"""Scoped memory with visibility, trust, reinforcement, TTL, and decay."""

from __future__ import annotations

import math
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

SCOPES = {"user", "project", "session", "mission", "team", "agent"}
STATUSES = {"active", "cooling", "archived"}


class ScopedMemory:
    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
        records: Iterable[dict[str, Any]] = (),
    ) -> None:
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.on_event = on_event or (lambda _event: None)
        self.records: dict[str, dict[str, Any]] = {}
        self.sequence = 0
        for row in records:
            self.restore(row)

    def write(self, **input_: Any) -> dict[str, Any]:
        scope = _scope(input_.get("scope"))
        namespace = str(input_.get("namespace", "")).strip()
        content = str(input_.get("content", "")).strip()
        if not namespace:
            raise ValueError("memory.namespace must be a non-empty string.")
        if not content:
            raise ValueError("memory.content must be a non-empty string.")
        now = _date(input_.get("now") or self.clock())
        self.sequence += 1
        memory_id = str(input_.get("id") or f"mem-{self.sequence}")
        if memory_id in self.records:
            raise ValueError(f"Duplicate memory id: {memory_id}")
        trust = "trusted" if input_.get("trust") == "trusted" else "untrusted"
        visibility = input_.get("visibility")
        if visibility is None:
            visibility = [namespace] if scope == "agent" else ["*"]
        if (
            not isinstance(visibility, list)
            or not visibility
            or not all(str(item).strip() for item in visibility)
        ):
            raise ValueError("memory.visibility must be a non-empty list of strings.")
        ttl_value = input_.get("ttlMs", 86_400_000)
        status = str(input_.get("status", "active"))
        if status not in STATUSES:
            raise ValueError(f"memory.status must be one of {', '.join(sorted(STATUSES))}.")
        row = {
            "id": memory_id,
            "scope": scope,
            "namespace": namespace,
            "kind": input_.get("kind", "context"),
            "content": content,
            "trust": trust,
            "confidence": _unit(input_.get("confidence"), 1),
            "relevance": _unit(input_.get("relevance"), 1),
            "sourceQuality": _unit(input_.get("sourceQuality"), 1 if trust == "trusted" else 0.5),
            "verifiedUtility": _unit(
                input_.get("verifiedUtility"), 1 if trust == "trusted" else 0.5
            ),
            "sensitivity": _unit(input_.get("sensitivity"), 0),
            "reuseCount": max(0, int(input_.get("reuseCount", 0))),
            "halfLifeMs": _positive(input_.get("halfLifeMs"), 3_600_000),
            "ttlMs": None
            if "ttlMs" in input_ and ttl_value is None
            else _positive(ttl_value, 86_400_000),
            "status": status,
            "visibility": list(dict.fromkeys(str(item).strip() for item in visibility)),
            "createdAt": _iso(now),
            "lastUsedAt": _iso(now),
            "metadata": deepcopy(input_.get("metadata", {}))
            if isinstance(input_.get("metadata", {}), dict)
            else {},
        }
        self.records[memory_id] = row
        self._emit("memory.write", row)
        return deepcopy(row)

    def query(
        self,
        *,
        scope: str,
        namespace: str,
        role: str | None = None,
        trusted_only: bool = False,
        max_sensitivity: float = 0.5,
        minimum_score: float = 0,
        limit: int = 10,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        _scope(scope)
        if not str(namespace).strip():
            raise ValueError("query.namespace must be a non-empty string.")
        at = _date(now or self.clock())
        rows = []
        for record in self.records.values():
            if (
                record["scope"] != scope
                or record["namespace"] != namespace
                or record["status"] not in {"active", "cooling"}
            ):
                continue
            if "*" not in record["visibility"] and (not role or role not in record["visibility"]):
                continue
            if trusted_only and record["trust"] != "trusted":
                continue
            if record["sensitivity"] > _unit(max_sensitivity, 0.5):
                continue
            row = {**record, "retentionScore": retention_score(record, at)}
            if row["retentionScore"] >= minimum_score:
                rows.append(row)
        rows.sort(key=lambda row: (-row["retentionScore"], row["id"]))
        rows = rows[: max(1, int(limit))]
        for row in rows:
            self.records[row["id"]]["lastUsedAt"] = _iso(at)
            self._emit(
                "memory.read",
                self.records[row["id"]],
                role=role or "*",
                retentionScore=row["retentionScore"],
            )
        return deepcopy(rows)

    def reinforce(
        self, memory_id: str, *, verified: bool, successful: bool, now: datetime | None = None
    ) -> dict[str, Any]:
        if memory_id not in self.records:
            raise ValueError(f"Unknown memory id: {memory_id}")
        row = self.records[memory_id]
        if not verified or not successful:
            self._emit("memory.reinforce_skipped", row)
            return deepcopy(row)
        row["reuseCount"] += 1
        row["verifiedUtility"] = min(1, row["verifiedUtility"] + 0.05)
        row["lastUsedAt"] = _iso(_date(now or self.clock()))
        row["status"] = "active"
        self._emit("memory.reinforced", row)
        return deepcopy(row)

    def decay(
        self,
        *,
        now: datetime | None = None,
        cooling_threshold: float = 0.4,
        archive_threshold: float = 0.2,
        delete_threshold: float = 0.05,
    ) -> dict[str, int]:
        at = _date(now or self.clock())
        summary = {"cooled": 0, "archived": 0, "deleted": 0}
        for memory_id, row in list(self.records.items()):
            age_ms = (at - _date(row["createdAt"])).total_seconds() * 1000
            expired = row["ttlMs"] is not None and age_ms >= row["ttlMs"]
            score = retention_score(row, at)
            if expired or score < delete_threshold:
                del self.records[memory_id]
                summary["deleted"] += 1
                self._emit("memory.deleted", row, expired=expired, retentionScore=score)
            elif score < archive_threshold and row["status"] != "archived":
                row["status"] = "archived"
                summary["archived"] += 1
                self._emit("memory.archived", row, retentionScore=score)
            elif score < cooling_threshold and row["status"] == "active":
                row["status"] = "cooling"
                summary["cooled"] += 1
                self._emit("memory.cooled", row, retentionScore=score)
        return summary

    def delete_scope(self, *, scope: str, namespace: str, reason: str = "scope_expired") -> int:
        _scope(scope)
        deleted = 0
        for memory_id, row in list(self.records.items()):
            if row["scope"] == scope and row["namespace"] == namespace:
                del self.records[memory_id]
                deleted += 1
                self._emit("memory.deleted", row, reason=reason)
        return deleted

    def snapshot(self, *, include_content: bool = False) -> list[dict[str, Any]]:
        rows = deepcopy(list(self.records.values()))
        if not include_content:
            for row in rows:
                row.pop("content", None)
        return rows

    def export(self) -> dict[str, Any]:
        return {"schemaVersion": 1, "records": self.snapshot(include_content=True)}

    def restore(self, row: dict[str, Any]) -> None:
        restored = _validate_restored_record(row)
        if restored["id"] in self.records:
            raise ValueError(f"Duplicate memory id: {restored['id']}")
        self.records[restored["id"]] = restored
        if restored["id"].startswith("mem-") and restored["id"][4:].isdigit():
            self.sequence = max(self.sequence, int(restored["id"][4:]))

    def _emit(self, type_: str, row: dict[str, Any], **extra: Any) -> None:
        self.on_event(
            {
                "type": type_,
                "memoryId": row["id"],
                "scope": row["scope"],
                "namespace": row["namespace"],
                "kind": row["kind"],
                "at": _iso(self.clock()),
                **extra,
            }
        )


def retention_score(record: dict[str, Any], now: datetime | None = None) -> float:
    at = _date(now or datetime.now(timezone.utc))
    used = _date(record.get("lastUsedAt") or record["createdAt"])
    age_ms = max(0.0, (at - used).total_seconds() * 1000)
    time_strength = 2 ** (-age_ms / _positive(record.get("halfLifeMs"), 1))
    reuse_boost = min(0.2, math.log2(1 + max(0, int(record.get("reuseCount", 0)))) * 0.04)
    base = (
        time_strength
        * _unit(record.get("confidence"), 1)
        * _unit(record.get("relevance"), 1)
        * _unit(record.get("sourceQuality"), 1)
        * _unit(record.get("verifiedUtility"), 1)
    )
    return max(0.0, min(1.0, base + reuse_boost - _unit(record.get("sensitivity"), 0) * 0.25))


def _scope(value: object) -> str:
    scope = str(value or "")
    if scope not in SCOPES:
        raise ValueError(f"memory.scope must be one of {', '.join(sorted(SCOPES))}.")
    return scope


def _unit(value: object, fallback: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return fallback


def _positive(value: object, fallback: float) -> float:
    try:
        number = float(value)
        return number if number > 0 else fallback
    except (TypeError, ValueError):
        return fallback


def _date(value: object) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("Invalid memory timestamp.")
    return result.replace(tzinfo=result.tzinfo or timezone.utc)


def _iso(value: datetime) -> str:
    return _date(value).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_restored_record(row: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("Invalid memory record.")
    required = {
        "id",
        "scope",
        "namespace",
        "kind",
        "content",
        "trust",
        "confidence",
        "relevance",
        "sourceQuality",
        "verifiedUtility",
        "sensitivity",
        "reuseCount",
        "halfLifeMs",
        "ttlMs",
        "status",
        "visibility",
        "createdAt",
        "lastUsedAt",
        "metadata",
    }
    missing = required - set(row)
    extra = set(row) - required
    if missing:
        raise ValueError("Invalid memory record: required fields are missing.")
    if extra:
        raise ValueError("Invalid memory record: unsupported fields are present.")
    if not isinstance(row["id"], str) or not row["id"].strip():
        raise ValueError("Invalid memory record id.")
    _scope(row["scope"])
    for key in ("namespace", "kind", "content"):
        if not isinstance(row[key], str) or not row[key].strip():
            raise ValueError(f"Invalid memory record {key}.")
    if row["trust"] not in {"trusted", "untrusted"}:
        raise ValueError("Invalid memory record trust.")
    for key in ("confidence", "relevance", "sourceQuality", "verifiedUtility", "sensitivity"):
        value = row[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ValueError(f"Invalid memory record {key}.")
    if (
        isinstance(row["reuseCount"], bool)
        or not isinstance(row["reuseCount"], int)
        or row["reuseCount"] < 0
    ):
        raise ValueError("Invalid memory record reuseCount.")
    if (
        isinstance(row["halfLifeMs"], bool)
        or not isinstance(row["halfLifeMs"], (int, float))
        or not math.isfinite(float(row["halfLifeMs"]))
        or row["halfLifeMs"] <= 0
    ):
        raise ValueError("Invalid memory record halfLifeMs.")
    if row["ttlMs"] is not None and (
        isinstance(row["ttlMs"], bool)
        or not isinstance(row["ttlMs"], (int, float))
        or not math.isfinite(float(row["ttlMs"]))
        or row["ttlMs"] <= 0
    ):
        raise ValueError("Invalid memory record ttlMs.")
    if row["status"] not in STATUSES:
        raise ValueError("Invalid memory record status.")
    if (
        not isinstance(row["visibility"], list)
        or not row["visibility"]
        or not all(isinstance(item, str) and item.strip() for item in row["visibility"])
    ):
        raise ValueError("Invalid memory record visibility.")
    _date(row["createdAt"])
    _date(row["lastUsedAt"])
    if not isinstance(row["metadata"], dict):
        raise ValueError("Invalid memory record metadata.")
    return deepcopy(row)
