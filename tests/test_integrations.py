from __future__ import annotations

from pathlib import Path

import pytest

from nestra.integrations import (
    IntegrationConflictError,
    install_integrations,
    integration_status,
)

ROOT = Path(__file__).resolve().parents[1]


def test_installs_native_adapters_for_supported_ai_clis(tmp_path: Path):
    records = install_integrations(home=tmp_path)

    assert [record["target"] for record in records] == ["codex", "claude", "gemini"]
    assert all(record["status"] == "installed" for record in records)
    codex = tmp_path / ".agents" / "skills" / "nestra" / "SKILL.md"
    claude = tmp_path / ".claude" / "skills" / "nestra" / "SKILL.md"
    gemini = tmp_path / ".gemini" / "commands" / "nestra.toml"
    assert "does not depend on a generated launcher" in codex.read_text(encoding="utf-8")
    assert "disable-model-invocation: true" in claude.read_text(encoding="utf-8")
    assert "{{args}}" in gemini.read_text(encoding="utf-8")
    assert all(record["status"] == "installed" for record in integration_status(home=tmp_path))


def test_install_is_idempotent_and_dry_run_does_not_write(tmp_path: Path):
    assert all(
        record["status"] == "would_install"
        for record in install_integrations(home=tmp_path, dry_run=True)
    )
    assert not (tmp_path / ".agents").exists()
    install_integrations(home=tmp_path)
    assert all(record["status"] == "unchanged" for record in install_integrations(home=tmp_path))


def test_modified_adapter_requires_force_and_is_backed_up(tmp_path: Path):
    install_integrations(["gemini"], home=tmp_path)
    command = tmp_path / ".gemini" / "commands" / "nestra.toml"
    command.write_text("user customization\n", encoding="utf-8")

    with pytest.raises(IntegrationConflictError, match="Refusing to overwrite"):
        install_integrations(["gemini"], home=tmp_path)

    [record] = install_integrations(["gemini"], home=tmp_path, force=True)
    assert record["status"] == "updated"
    assert len(record["backups"]) == 1
    backup = Path(record["backups"][0])
    assert backup.read_text(encoding="utf-8") == "user customization\n"
    assert "{{args}}" in command.read_text(encoding="utf-8")


def test_repository_and_packaged_codex_skill_are_identical():
    repository_skill = ROOT / ".agents" / "skills" / "nestra" / "SKILL.md"
    packaged_skill = ROOT / "src" / "nestra" / "resources" / "skills" / "nestra" / "SKILL.md"
    assert repository_skill.read_text(encoding="utf-8") == packaged_skill.read_text(
        encoding="utf-8"
    )


def test_single_target_can_be_passed_as_a_string(tmp_path: Path):
    [record] = install_integrations("claude", home=tmp_path)
    assert record["target"] == "claude"
    assert not (tmp_path / ".agents").exists()


def test_installed_adapter_contains_module_fallback_for_blocked_launchers(tmp_path: Path):
    executable = tmp_path / "Program Files" / "Python" / "python.exe"
    install_integrations("codex", home=tmp_path, python_executable=executable)
    skill = (tmp_path / ".agents" / "skills" / "nestra" / "SKILL.md").read_text(encoding="utf-8")
    assert f'"{executable.resolve()}" -m nestra' in skill
    assert "python -m nestra" not in skill
    assert "`nestra list`" not in skill
    [status] = integration_status("codex", home=tmp_path, python_executable=executable)
    assert status["status"] == "installed"
