"""Migração preserva dados, favoritos, autenticação e o significado dos caminhos MCP."""

import json
import os
import subprocess
import sys
from dataclasses import asdict
from unittest.mock import Mock

import pytest

from ataflow.mcp.settings import MCPSettings
from ataflow.storage import ensure_data_layout
from ataflow.summaries.catalog import ModelPreferences, PreferenceStore


def legacy_home(home, summaries_dir="transcricoes"):
    folder = home / "transcricoes"
    folder.mkdir()
    (folder / "reunião.txt").write_text("Texto original", encoding="utf-8")
    (folder / "reunião-resumo.md").write_text("# Ata original", encoding="utf-8")
    (home / "transcriber.log").write_text("Log original", encoding="utf-8")
    (home / ".env").write_text("GEMINI_API_KEY=synthetic-only", encoding="utf-8")
    PreferenceStore(home / "model_preferences.json").save(
        ModelPreferences(
            configured=True, favorites=["gemini-favorito"], default_model="gemini-favorito"
        )
    )
    settings = MCPSettings(
        enabled=True,
        network_enabled=True,
        summaries_dir=summaries_dir,
        http_token="synthetic-token-for-migration-tests-1234",
    )
    (home / "mcp_preferences.json").write_text(json.dumps(asdict(settings)), encoding="utf-8")
    return settings


@pytest.mark.parametrize("relative", ["transcricoes", "compartilhados", "transcricoes/subpasta"])
def test_migration_preserves_settings_and_relative_paths(tmp_path, relative):
    previous = legacy_home(tmp_path, relative)
    original_models = (tmp_path / "model_preferences.json").read_bytes()
    original_env = (tmp_path / ".env").read_bytes()
    data = ensure_data_layout(tmp_path)
    settings = MCPSettings(
        **json.loads((data / "mcp_preferences.json").read_text(encoding="utf-8"))
    )
    assert settings.http_token == previous.http_token
    assert settings.enabled and settings.network_enabled
    expected = data / relative if relative.startswith("transcricoes") else tmp_path / relative
    assert settings.directory(data) == expected.resolve()
    assert (data / "model_preferences.json").read_bytes() == original_models
    assert (tmp_path / ".env").read_bytes() == original_env
    assert (data / "transcricoes" / "reunião.txt").read_text(encoding="utf-8") == "Texto original"
    assert (data / "logs" / "transcriber.log").read_text(encoding="utf-8") == "Log original"
    assert not (tmp_path / "transcricoes").exists()
    assert not (tmp_path / "mcp_preferences.json").exists()
    assert ensure_data_layout(tmp_path) == data
    assert not (data / ".migration.lock").exists()


@pytest.mark.parametrize("name", ["transcricoes", "model_preferences.json", "mcp_preferences.json"])
def test_conflict_leaves_every_original_untouched(tmp_path, name):
    legacy_home(tmp_path)
    data = tmp_path / "var"
    data.mkdir()
    target = data / name
    if name == "transcricoes":
        target.mkdir()
    else:
        target.write_text("Conteúdo existente", encoding="utf-8")
    original = (tmp_path / "mcp_preferences.json").read_bytes()
    with pytest.raises(ValueError, match="Nenhum arquivo foi substituído"):
        ensure_data_layout(tmp_path)
    assert (tmp_path / "mcp_preferences.json").read_bytes() == original
    assert (tmp_path / "model_preferences.json").exists()
    assert (tmp_path / "transcricoes" / "reunião.txt").exists()
    assert target.exists()


@pytest.mark.parametrize("name", ["model_preferences.json", "mcp_preferences.json"])
def test_invalid_configuration_blocks_migration(tmp_path, name):
    legacy_home(tmp_path)
    (tmp_path / name).write_text("invalid", encoding="utf-8")
    with pytest.raises(ValueError):
        ensure_data_layout(tmp_path)
    assert (tmp_path / name).read_text(encoding="utf-8") == "invalid"
    assert (tmp_path / "transcricoes").exists()
    assert not (tmp_path / "var" / "transcricoes").exists()


def test_write_failure_rolls_back_moves(tmp_path, monkeypatch):
    legacy_home(tmp_path)
    original = (tmp_path / "mcp_preferences.json").read_bytes()
    monkeypatch.setattr("ataflow.storage.os.replace", Mock(side_effect=OSError("Sem espaço")))
    with pytest.raises(OSError):
        ensure_data_layout(tmp_path)
    assert (tmp_path / "mcp_preferences.json").read_bytes() == original
    assert (tmp_path / "model_preferences.json").exists()
    assert (tmp_path / "transcricoes" / "reunião.txt").exists()
    assert not list((tmp_path / "var").glob("*.tmp"))


@pytest.mark.parametrize("external", [False, True])
def test_absolute_shared_directory_preserves_destination(tmp_path, external):
    home = tmp_path / "home"
    home.mkdir()
    shared = tmp_path / "shared" if external else home / "transcricoes"
    if external:
        shared.mkdir()
        (shared / "externa-resumo.md").write_text("Ata externa", encoding="utf-8")
    legacy_home(home, str(shared))
    data = ensure_data_layout(home)
    migrated = MCPSettings(
        **json.loads((data / "mcp_preferences.json").read_text(encoding="utf-8"))
    )
    assert migrated.directory(data) == (shared if external else data / "transcricoes")
    if external:
        assert (shared / "externa-resumo.md").read_text(encoding="utf-8") == "Ata externa"


def test_legacy_mcp_config_argument_redirects_to_migrated_store(tmp_path):
    legacy_home(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; from ataflow.mcp.settings import MCPSettingsStore; "
            "from ataflow.paths import PROJECT_DIR; "
            "old = MCPSettingsStore(PROJECT_DIR / 'mcp_preferences.json'); "
            "new = MCPSettingsStore(); assert old.path == new.path; "
            "assert old.load().http_token == new.load().http_token; "
            "assert old.load().enabled; print('compatible')",
        ],
        cwd=tmp_path,
        env={**os.environ, "ATAFLOW_HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "compatible" in result.stdout


def test_concurrent_migration_blocks_access_without_modifying_sources(tmp_path):
    legacy_home(tmp_path)
    (tmp_path / "var").mkdir()
    (tmp_path / "var" / ".migration.lock").touch()
    with pytest.raises(ValueError, match="Migração em andamento"):
        ensure_data_layout(tmp_path)
    assert (tmp_path / "transcricoes").exists()
