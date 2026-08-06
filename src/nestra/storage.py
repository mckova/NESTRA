"""Atomic filesystem store for versioned project-memory snapshots."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .audit import append_audit
from .project_memory import ProjectMemoryIndex, restore_project_memory
from .security import validate_project_id


class ProjectNotFoundError(FileNotFoundError):
    code = "project_not_found"


class FileProjectStore:
    def __init__(
        self, root: str | Path = ".nestra", *, clock: Callable[[], datetime] | None = None
    ) -> None:
        self.root = Path(root).resolve()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def save(self, project: ProjectMemoryIndex | dict[str, Any]) -> dict[str, Any]:
        snapshot = project.export() if isinstance(project, ProjectMemoryIndex) else project
        project_id = validate_project_id(
            snapshot.get("projectId") if isinstance(snapshot, dict) else None
        )
        restore_project_memory(snapshot)
        directory = self.root / "projects"
        directory.mkdir(parents=True, exist_ok=True)
        target = self.project_path(project_id)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{project_id}.", suffix=".tmp", dir=directory
        )
        try:
            if os.name != "nt":
                os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(snapshot, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
        self.audit(
            {"type": "project.saved", "projectId": project_id, "facts": len(snapshot["facts"])}
        )
        return {"projectId": project_id, "path": str(target), "stats": dict(snapshot["stats"])}

    def load(self, project_id: str) -> ProjectMemoryIndex:
        target = self.project_path(project_id)
        try:
            snapshot = json.loads(target.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ProjectNotFoundError(f"Unknown project: {project_id}") from error
        except json.JSONDecodeError as error:
            raise ValueError(f"Stored project {project_id} contains invalid JSON.") from error
        if snapshot.get("projectId") != validate_project_id(project_id):
            raise ValueError(f"Stored project id mismatch for {project_id}.")
        return restore_project_memory(snapshot)

    def inspect(self, project_id: str) -> dict[str, Any]:
        snapshot = self.load(project_id).export()
        stat = self.project_path(project_id).stat()
        return {
            "schemaVersion": snapshot["schemaVersion"],
            "projectId": snapshot["projectId"],
            "compiledAt": snapshot["compiledAt"],
            "stats": snapshot["stats"],
            "bytes": stat.st_size,
            "updatedAt": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }

    def list(self) -> list[str]:
        directory = self.root / "projects"
        directory.mkdir(parents=True, exist_ok=True)
        return sorted(path.stem for path in directory.glob("*.json") if path.is_file())

    def delete(self, project_id: str) -> bool:
        try:
            self.project_path(project_id).unlink()
        except FileNotFoundError:
            return False
        self.audit({"type": "project.deleted", "projectId": project_id})
        return True

    def audit(self, event: dict[str, Any]) -> dict[str, Any]:
        return append_audit(self.root / "audit.jsonl", event, self.clock)

    def project_path(self, project_id: str) -> Path:
        return self.root / "projects" / f"{validate_project_id(project_id)}.json"
