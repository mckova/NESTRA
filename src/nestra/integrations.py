"""Safe installers for native NESTRA commands in supported AI CLIs."""

from __future__ import annotations

import os
import shlex
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Iterable

SUPPORTED_INTEGRATIONS = ("codex", "claude", "gemini")

_INVOCATIONS = {
    "codex": "$nestra (or select NESTRA from /skills)",
    "claude": "/nestra",
    "gemini": "/nestra",
}


class IntegrationConflictError(FileExistsError):
    """Raised when installation would overwrite user-owned integration files."""


@dataclass(frozen=True)
class _Artifact:
    target: str
    resource: str
    destination: Path


def install_integrations(
    targets: Iterable[str] | None = None,
    *,
    home: str | Path | None = None,
    force: bool = False,
    dry_run: bool = False,
    python_executable: str | Path | None = None,
) -> list[dict[str, object]]:
    """Install native NESTRA adapters without silently replacing existing files."""

    selected = _validate_targets(targets)
    root = Path(home).expanduser().resolve() if home is not None else Path.home().resolve()
    command = _module_command(python_executable)
    artifacts = [artifact for target in selected for artifact in _artifacts(target, root)]
    conflicts = [
        artifact.destination
        for artifact in artifacts
        if artifact.destination.exists()
        and artifact.destination.read_text(encoding="utf-8")
        != _render_resource(artifact.resource, command)
    ]
    if conflicts and not force:
        rendered = ", ".join(str(path) for path in conflicts)
        raise IntegrationConflictError(
            f"Refusing to overwrite modified integration files: {rendered}. "
            "Re-run with --force to preserve backups and replace them."
        )

    records: list[dict[str, object]] = []
    for target in selected:
        target_artifacts = [artifact for artifact in artifacts if artifact.target == target]
        statuses: list[str] = []
        paths: list[str] = []
        backups: list[str] = []
        for artifact in target_artifacts:
            content = _render_resource(artifact.resource, command)
            paths.append(str(artifact.destination))
            if (
                artifact.destination.exists()
                and artifact.destination.read_text(encoding="utf-8") == content
            ):
                statuses.append("unchanged")
                continue
            replacing = artifact.destination.exists()
            statuses.append(
                "would_update"
                if dry_run and replacing
                else "would_install"
                if dry_run
                else "updated"
                if replacing
                else "installed"
            )
            if dry_run:
                continue
            if replacing:
                backup = _backup_path(artifact.destination)
                _atomic_write(backup, artifact.destination.read_text(encoding="utf-8"))
                backups.append(str(backup))
            _atomic_write(artifact.destination, content)
        records.append(
            {
                "target": target,
                "status": _target_status(statuses),
                "invoke": _INVOCATIONS[target],
                "paths": paths,
                "backups": backups,
            }
        )
    return records


def integration_status(
    targets: Iterable[str] | None = None,
    *,
    home: str | Path | None = None,
    python_executable: str | Path | None = None,
) -> list[dict[str, object]]:
    """Return whether every native adapter matches the packaged NESTRA version."""

    selected = _validate_targets(targets)
    root = Path(home).expanduser().resolve() if home is not None else Path.home().resolve()
    command = _module_command(python_executable)
    records: list[dict[str, object]] = []
    for target in selected:
        artifacts = _artifacts(target, root)
        states = []
        for artifact in artifacts:
            if not artifact.destination.exists():
                states.append("missing")
            elif artifact.destination.read_text(encoding="utf-8") == _render_resource(
                artifact.resource, command
            ):
                states.append("installed")
            else:
                states.append("modified")
        status = states[0] if len(set(states)) == 1 else "partial"
        records.append(
            {
                "target": target,
                "status": status,
                "invoke": _INVOCATIONS[target],
                "paths": [str(artifact.destination) for artifact in artifacts],
            }
        )
    return records


def _validate_targets(targets: Iterable[str] | None) -> tuple[str, ...]:
    candidates = (targets,) if isinstance(targets, str) else targets
    selected = tuple(dict.fromkeys(candidates or SUPPORTED_INTEGRATIONS))
    unknown = [target for target in selected if target not in SUPPORTED_INTEGRATIONS]
    if unknown:
        raise ValueError(f"Unsupported AI CLI integration: {', '.join(unknown)}")
    return selected


def _artifacts(target: str, home: Path) -> list[_Artifact]:
    if target == "codex":
        base = home / ".agents" / "skills" / "nestra"
        return [
            _Artifact(target, "resources/skills/nestra/SKILL.md", base / "SKILL.md"),
            _Artifact(
                target,
                "resources/skills/nestra/agents/openai.yaml",
                base / "agents" / "openai.yaml",
            ),
        ]
    if target == "claude":
        return [
            _Artifact(
                target,
                "resources/claude/skills/nestra/SKILL.md",
                home / ".claude" / "skills" / "nestra" / "SKILL.md",
            )
        ]
    return [
        _Artifact(
            target,
            "resources/gemini/commands/nestra.toml",
            home / ".gemini" / "commands" / "nestra.toml",
        )
    ]


def _resource_text(relative: str) -> str:
    resource = files("nestra")
    for part in relative.split("/"):
        resource = resource.joinpath(part)
    return resource.read_text(encoding="utf-8")


def _render_resource(relative: str, command: str) -> str:
    return _resource_text(relative).replace("python -m nestra", command)


def _module_command(python_executable: str | Path | None) -> str:
    executable = str(Path(python_executable or sys.executable).resolve())
    quoted = f'"{executable}"' if os.name == "nt" else shlex.quote(executable)
    return f"{quoted} -m nestra"


def _target_status(statuses: list[str]) -> str:
    changed = [status for status in statuses if status != "unchanged"]
    if not changed:
        return "unchanged"
    if all(status == changed[0] for status in changed):
        return changed[0]
    return "updated"


def _backup_path(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = path.with_name(f"{path.name}.bak.{stamp}")
    suffix = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.bak.{stamp}.{suffix}")
        suffix += 1
    return candidate


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        if os.name != "nt":
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
