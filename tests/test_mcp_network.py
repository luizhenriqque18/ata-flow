from __future__ import annotations

import json
import socket
import tomllib
from dataclasses import replace

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from mcp_network import MCPHTTPService
from mcp_settings import MCPSettings, MCPSettingsStore, client_config


@pytest.fixture
def network_store(tmp_path):
    (tmp_path / "resumos").mkdir()
    (tmp_path / "resumos" / "reuniao-resumo.md").write_text(
        "# Reunião\nDecisão: testar a rede.",
        encoding="utf-8",
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    store = MCPSettingsStore(tmp_path / "settings.json")
    store.save(
        MCPSettings(
            enabled=True,
            summaries_dir="resumos",
            network_enabled=True,
            http_port=port,
            http_token="synthetic-token-for-network-testing-1234",
        )
    )
    return store


@pytest.mark.asyncio
async def test_real_http_mcp_and_lifecycle(network_store):
    network_store.save(replace(network_store.load(), http_host="0.0.0.0"))
    service = MCPHTTPService(network_store)
    settings = network_store.load()
    try:
        await service.apply()
        assert service.running
        original_task = service.task
        await service.apply()
        assert service.task is original_task
        async with (
            httpx.AsyncClient(
                headers={"Authorization": f"Bearer {settings.http_token}"},
                timeout=5,
                trust_env=False,
            ) as http,
            streamable_http_client(settings.http_url(), http_client=http) as (read, write, _),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            tools = await session.list_tools()
            assert {t.name for t in tools.tools} == {"search_summaries", "read_summary"}
            result = await session.call_tool("read_summary", {"summary_id": "reuniao-resumo.md"})
            assert not result.isError
            assert "testar a rede" in str(result)
        # Aplicar desativação para de escutar, não apenas esconde as ferramentas.
        network_store.save(replace(settings, network_enabled=False))
        await service.apply()
        assert not service.running
        async with httpx.AsyncClient(timeout=1, trust_env=False) as client:
            with pytest.raises((httpx.ConnectError, httpx.ConnectTimeout)):
                await client.get(settings.http_url())
        network_store.save(settings)
        await service.apply()
        assert service.running
    finally:
        await service.stop()
    assert not service.running


@pytest.mark.asyncio
async def test_auth_rotation_revocation_and_host_origin(network_store):
    settings = network_store.load()
    service = MCPHTTPService(network_store)
    try:
        await service.apply()
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            url = settings.http_url()
            assert (await client.get(url)).status_code == 401
            assert (
                await client.get(url, headers={"Authorization": "Bearer wrong"})
            ).status_code == 401
            headers = {
                "Authorization": f"Bearer {settings.http_token}",
                "Accept": "text/event-stream",
            }
            assert (
                await client.get(url, headers={**headers, "Host": "attacker.example"})
            ).status_code == 421
            assert (
                await client.get(url, headers={**headers, "Origin": "https://attacker.example"})
            ).status_code == 403
            rotated = replace(settings, http_token="rotated-synthetic-token-for-testing-1234")
            network_store.save(rotated)
            assert (await client.get(url, headers=headers)).status_code == 401
            headers["Authorization"] = f"Bearer {rotated.http_token}"
            async with client.stream("GET", url, headers=headers) as response:
                assert response.status_code == 200
            network_store.save(replace(rotated, network_enabled=False))
            assert (await client.get(url, headers=headers)).status_code == 503
            network_store.save(replace(rotated, enabled=False))
            assert (await client.get(url, headers=headers)).status_code == 503
            network_store.path.write_text("invalid config", encoding="utf-8")
            assert (await client.get(url, headers=headers)).status_code == 503
            with pytest.raises(ValueError):
                await service.apply()
            assert not service.running
    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_busy_port_reports_error_and_recovers(network_store):
    settings = network_store.load()
    service = MCPHTTPService(network_store)
    with socket.socket() as blocker:
        blocker.bind((settings.http_host, settings.http_port))
        blocker.listen()
        with pytest.raises(OSError):
            await service.apply()
        assert not service.running
    try:
        await service.apply()
        assert service.running
    finally:
        await service.stop()


def test_network_config_does_not_embed_token(network_store):
    settings = network_store.load()
    toml = client_config(network_store, "http-codex")
    config = tomllib.loads(toml)["mcp_servers"]["ataflow"]
    assert config["url"] == settings.http_url()
    assert config["bearer_token_env_var"] == "ATAFLOW_MCP_TOKEN"
    assert settings.http_token not in toml
    raw = client_config(network_store, "http-json")
    assert json.loads(raw)["mcpServers"]["ataflow"]["url"] == settings.http_url()
    assert settings.http_token not in raw


@pytest.mark.asyncio
async def test_app_starts_saved_network_and_closes_listener(network_store, tmp_path, monkeypatch):
    from argparse import Namespace

    import main

    monkeypatch.chdir(tmp_path)
    app = main.AtaFlowApp(Namespace(), {})
    service = MCPHTTPService(network_store)
    app.mcp_http_service = service
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        assert service.running
    assert not service.running


@pytest.mark.parametrize(
    "changes",
    [
        {"network_enabled": 1},
        {"http_port": 0},
        {"http_port": True},
        {"http_host": "https://example.com"},
        {"http_token": "short"},
        {"http_token": ""},
        {"http_public_host": "0.0.0.0"},
        {"http_public_host": "http://192.168.1.10"},
        {"http_host": 1},
        {"http_public_host": "::invalid"},
    ],
)
def test_invalid_network_settings_preserve_file(network_store, changes):
    previous = network_store.path.read_bytes()
    with pytest.raises(ValueError):
        network_store.save(replace(network_store.load(), **changes))
    assert network_store.path.read_bytes() == previous
