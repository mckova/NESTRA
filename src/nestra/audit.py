"""Content-safe append-only audit helpers."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable

SECRET_KEY = re.compile(
    r"authorization|api[-_]?key|secret|password|access[-_]?token|refresh[-_]?token|cookie", re.I
)
CONTENT_KEY = re.compile(
    r"^(prompt|input|output|content|text|question|answer|evidence|memory|reusableContext|messages)$",
    re.I,
)
_LOCKS_GUARD = Lock()
_PATH_LOCKS: dict[Path, Lock] = {}


def redact(value: Any, key: str = "") -> Any:
    if SECRET_KEY.search(key) or key.lower() == "token" or CONTENT_KEY.fullmatch(key):
        return "[REDACTED]"
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {child_key: redact(child, child_key) for child_key, child in value.items()}
    return value


def append_audit(
    file_path: str | Path, event: dict[str, Any], clock: Callable[[], datetime] | None = None
) -> dict[str, Any]:
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    safe = redact(
        {
            "schemaVersion": 1,
            "at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            **event,
        }
    )
    target = Path(file_path)
    resolved = target.resolve()
    with _LOCKS_GUARD:
        lock = _PATH_LOCKS.setdefault(resolved, Lock())
    with lock:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(safe, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
    return safe
