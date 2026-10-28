from __future__ import annotations

import json
import sys
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ataflow_mcp import SummaryLibrary
from mcp_settings import PROJECT_DIR, MCPSettings, MCPSettingsStore, client_config


@pytest.fixture
def library(tmp_path):
    folder = tmp_path / "resumos"
    folder.mkdir()
    store = MCPSettingsStore(tmp_path / "preferences.json")
    store.save(MCPSettings(enabled=True, summaries_dir="resumos", max_results=1, max_chars=1000))
    (folder / "transcricao_2026-10-28-resumo.md").write_text(
        "# Orçamento\nDecisão: aprovar ação.",
        encoding="utf-8",
    )
    (folder / "transcricao_2026-10-27-resumo.md").write_text("a" * 2300, encoding="utf-8")
    (folder / "segredo.txt").write_text("segredo", encoding="utf-8")
    (folder / "outro.md").write_text("não é resumo", encoding="utf-8")
    return SummaryLibrary(store)


def test_search_read_and_pagination(library):
    page = library.search()
    assert page["summaries"][0]["id"] == "transcricao_2026-10-28-resumo.md"
    assert page["next_offset"] == 1
    assert library.search(offset=1)["next_offset"] is None
    assert len(library.search("ORÇAMENTO")["summaries"]) == 1
    assert not library.search("inexistente")["summaries"]
    assert "aprovar" in library.read(page["summaries"][0]["id"])["content"]
    summary_id = library.search(offset=1)["summaries"][0]["id"]
    parts = [library.read(summary_id, offset) for offset in (0, 1000, 2000)]
    assert [p["next_offset"] for p in parts] == [1000, 2000, None]
    assert "".join(p["content"] for p in parts) == "a" * 2300


def test_live_disable_and_configuration_changes(library):
    store = library.store
    settings = store.load()
    store.save(replace(settings, enabled=False))
    with pytest.raises(ValueError, match="desativado"):
        library.search()
    with pytest.raises(ValueError, match="desativado"):
        library.read("transcricao_2026-10-28-resumo.md")
    store.save(replace(settings, max_results=10))
    assert len(library.search()["summaries"]) == 2
    store.path.write_text('{"enabled": "yes"}', encoding="utf-8")
    with pytest.raises(ValueError, match="inválida"):
        library.search()
    store.path.unlink()
    with pytest.raises(ValueError, match="desativado"):
        library.search()


@pytest.mark.parametrize(
    "name",
    [
        "../escape-resumo.md",
        "..\\escape-resumo.md",
        "C:escape-resumo.md",
        ".env",
        "segredo.txt",
        "outro.md",
        "ausente-resumo.md",
    ],
)
def test_reject_paths_and_non_summaries(library, name):
    with pytest.raises(ValueError):
        library.read(name)


def test_reject_symlink(library, tmp_path):
    external = tmp_path / "external.md"
    external.write_text("privado", encoding="utf-8")
    link = library.store.load().directory(tmp_path) / "external-resumo.md"
    try:
        link.symlink_to(external)
    except OSError:
        pytest.skip("Criação de symlinks indisponível no Windows atual")
    with pytest.raises(ValueError):
        library.read(link.name)
    assert all(p["id"] != link.name for p in library.search()["summaries"])


@pytest.mark.parametrize(
    "changes",
    [
        {"enabled": 1},
        {"max_results": 0},
        {"max_results": True},
        {"max_chars": 999},
        {"summaries_dir": ""},
    ],
)
def test_settings_validation_preserves_file(library, changes):
    previous = library.store.path.read_bytes()
    with pytest.raises(ValueError):
        library.store.save(replace(library.store.load(), **changes))
    assert library.store.path.read_bytes() == previous


def test_connection_formats(library):
    entry = json.loads(client_config(library.store))["mcpServers"]["ataflow"]
    toml_entry = tomllib.loads(client_config(library.store, "codex"))["mcp_servers"]["ataflow"]
    assert entry == toml_entry
    assert Path(entry["command"]).is_absolute()
    assert entry["args"][-1] == str(library.store.path)


@pytest.mark.asyncio
async def test_real_stdio_client_and_live_revocation(library, tmp_path):
    # Real protocolo: inicialização, descoberta e ferramentas a partir de outro cwd.
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(PROJECT_DIR / "ataflow_mcp.py"), "--config", str(library.store.path)],
        cwd=str(tmp_path),
    )
    async with stdio_client(parameters) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        listing = await session.list_tools()
        assert {t.name for t in listing.tools} == {"search_summaries", "read_summary"}
        assert all(t.annotations.readOnlyHint for t in listing.tools)
        result = await session.call_tool("search_summaries", {"query": "Orçamento"})
        assert not result.isError
        assert "transcricao_2026-10-28-resumo.md" in str(result)
        result = await session.call_tool(
            "read_summary",
            {
                "summary_id": "transcricao_2026-10-28-resumo.md",
            },
        )
        assert not result.isError
        assert "aprovar" in str(result)
        library.store.save(replace(library.store.load(), enabled=False))
        denied = await session.call_tool("search_summaries", {})
        assert denied.isError
        assert "desativado" in str(denied)
